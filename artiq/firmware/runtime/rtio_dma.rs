use core::mem;
use alloc::{vec::Vec, string::String, collections::btree_map::BTreeMap};
use sched::{Io, Mutex, Error as SchedError};

const ALIGNMENT: usize = 64;

#[cfg(has_drtio)]
pub mod remote_dma {
    use super::*;
    use board_artiq::drtio_routing::RoutingTable;
    use rtio_mgt::drtio;
    use board_misoc::clock;

    #[derive(Debug, PartialEq, Clone)]
    pub enum RemoteState {
        NotLoaded,
        Loaded,
        PlaybackEnded { error: u8, channel: u32, timestamp: u64 }
    }

    #[derive(Debug, Clone)]
    struct RemoteTrace {
        trace: Vec<u8>,
        pub state: RemoteState
    }

    impl From<Vec<u8>> for RemoteTrace {
        fn from(trace: Vec<u8>) -> Self {
            RemoteTrace {
                trace: trace,
                state: RemoteState::NotLoaded
            }
        }
    }
    
    impl RemoteTrace {
        pub fn get_trace(&self) -> &Vec<u8> {
            &self.trace
        }
    }

    #[derive(Fail, Debug)]
    pub enum Error {
        #[fail(display = "Timed out waiting for DMA results")]
        Timeout,
        #[fail(display = "DDMA trace is in incorrect state for the given operation")]
        IncorrectState,
        #[fail(display = "scheduler error: {}", _0)]
        SchedError(#[cause] SchedError),
        #[fail(display = "DRTIO error: {}", _0)]
        DrtioError(#[cause] drtio::Error),
    }

    impl From<drtio::Error> for Error {
        fn from(value: drtio::Error) -> Error {
            match value {
                drtio::Error::SchedError(x) => Error::SchedError(x),
                x => Error::DrtioError(x),
            }
        }
    }

    impl From<SchedError> for Error {
        fn from(value: SchedError) -> Error {
                Error::SchedError(value)
        }
    }

    // remote traces map. ID -> destination, trace pair
    static mut TRACES: BTreeMap<u32, BTreeMap<u8, RemoteTrace>> = BTreeMap::new();

    pub fn add_traces(io: &Io, ddma_mutex: &Mutex, id: u32, traces: BTreeMap<u8, Vec<u8>>
    ) -> Result<(), SchedError> {
        let _lock = ddma_mutex.lock(io)?;
        let mut trace_map: BTreeMap<u8, RemoteTrace> = BTreeMap::new();
        for (destination, trace) in traces {
            trace_map.insert(destination, trace.into());
        }
        unsafe { TRACES.insert(id, trace_map); }
        Ok(())
    }

    pub fn await_done(io: &Io, ddma_mutex: &Mutex, id: u32, timeout: u64) -> Result<RemoteState, Error> {
        let max_time = clock::get_ms() + timeout as u64;
        io.until(|| {
            if clock::get_ms() > max_time {
                return true;
            }
            if ddma_mutex.test_lock() {
                // cannot lock again within io.until - scheduler guarantees
                // that it will not be interrupted - so only test the lock
                return false;
            }
            let traces = unsafe { TRACES.get(&id).unwrap() };
            for (_dest, trace) in traces {
                match trace.state {
                    RemoteState::PlaybackEnded {error: _, channel: _, timestamp: _} => (),
                    _ => return false
                }
            }
            true
        })?;
        if clock::get_ms() > max_time {
            error!("Remote DMA await done timed out");
            return Err(Error::Timeout);
        }
        // clear the internal state, and if there have been any errors, return one of them
        let mut playback_state: RemoteState = RemoteState::PlaybackEnded { error: 0, channel: 0, timestamp: 0 };
        {
            let _lock = ddma_mutex.lock(io)?;
            let traces = unsafe { TRACES.get_mut(&id).unwrap() };
            for (_dest, trace) in traces {
                match trace.state {
                    RemoteState::PlaybackEnded {error: e, channel: _c, timestamp: _ts} => if e != 0 { playback_state = trace.state.clone(); },
                    _ => (),
                }
                trace.state = RemoteState::Loaded;
            }
        }
        Ok(playback_state)
    }

    pub fn erase(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
            routing_table: &RoutingTable, id: u32) -> Result<(), Error> {
        let _lock = ddma_mutex.lock(io)?;
        let destinations = unsafe { TRACES.get(&id).unwrap() };
        for destination in destinations.keys() {
            match drtio::ddma_send_erase(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, id, *destination) {
                Ok(_) => (),
                Err(e) => error!("Error erasing trace on DMA: {}", e)
            } 
        }
        unsafe { TRACES.remove(&id); }
        Ok(())
    }

    pub fn upload_traces(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
            routing_table: &RoutingTable, id: u32) -> Result<(), Error> {
        let _lock = ddma_mutex.lock(io)?;
        let traces = unsafe { TRACES.get_mut(&id).unwrap() };
        for (destination, mut trace) in traces {
            drtio::ddma_upload_trace(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, id, *destination, trace.get_trace())?;
            trace.state = RemoteState::Loaded;
        }
        Ok(())
    }

    pub fn playback(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
            routing_table: &RoutingTable, id: u32, timestamp: u64) -> Result<(), Error>{
        // triggers playback on satellites
        let destinations = unsafe { 
            let _lock = ddma_mutex.lock(io)?;
            TRACES.get(&id).unwrap() };
        for (destination, trace) in destinations {
            {
                // need to drop the lock before sending the playback request to avoid a deadlock
                // if a PlaybackStatus is returned from another satellite in the meanwhile.
                let _lock = ddma_mutex.lock(io)?;
                if trace.state != RemoteState::Loaded {
                    error!("Destination {} not ready for DMA, state: {:?}", *destination, trace.state);
                    return Err(Error::IncorrectState);
                }
            }
            drtio::ddma_send_playback(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, id, *destination, timestamp)?;
        }
        Ok(())
    }

    pub fn playback_done(io: &Io, ddma_mutex: &Mutex, 
            id: u32, source: u8, error: u8, channel: u32, timestamp: u64) {
        // called upon receiving PlaybackDone aux packet
        let _lock = ddma_mutex.lock(io).unwrap();
        let mut trace = unsafe { TRACES.get_mut(&id).unwrap().get_mut(&source).unwrap() };
        trace.state = RemoteState::PlaybackEnded {
            error: error, 
            channel: channel, 
            timestamp: timestamp 
        };
    }

    pub fn destination_changed(io: &Io, aux_mutex: &Mutex, ddma_mutex: &Mutex, subkernel_mutex: &Mutex, 
        routing_table: &RoutingTable, destination: u8, up: bool) {
        // update state of the destination, resend traces if it's up
        let _lock = ddma_mutex.lock(io).unwrap();
        let traces_iter = unsafe { TRACES.iter_mut() };
        for (id, dest_traces) in traces_iter {
            if let Some(trace) = dest_traces.get_mut(&destination) {
                if up {
                    match drtio::ddma_upload_trace(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, *id, destination, trace.get_trace())
                    {
                        Ok(_) => trace.state = RemoteState::Loaded,
                        Err(e) => error!("Error adding DMA trace on destination {}: {}", destination, e)
                    }
                } else {
                    trace.state = RemoteState::NotLoaded;
                }
            }
        }
    }

    pub fn has_remote_traces(io: &Io, ddma_mutex: &Mutex, id: u32) -> Result<bool, Error> {
        let _lock = ddma_mutex.lock(io)?;
        let trace_list = unsafe { TRACES.get(&id).unwrap() };
        Ok(!trace_list.is_empty())
    }

}


#[derive(Debug)]
struct LocalEntry {
    trace: Vec<u8>,
    padding_len: usize,
    duration: u64
}

#[derive(Debug)]
pub struct Manager {
    entries: BTreeMap<u32, LocalEntry>,
    name_map: BTreeMap<String, u32>,
    recording_name: String,
    recording_trace: Vec<u8>
}

impl Manager {
    pub fn new() -> Manager {
        Manager {
            entries: BTreeMap::new(),
            name_map: BTreeMap::new(),
            recording_trace: Vec::new(),
            recording_name: String::new()
        }
    }

    pub fn record_start(&mut self, name: &str) -> Option<u32> {
        self.recording_name = String::from(name);
        self.recording_trace = Vec::new();
        if let Some(id) = self.name_map.get(&self.recording_name) {
            // replacing a trace
            let old_id = id.clone();
            self.entries.remove(&id);
            self.name_map.remove(&self.recording_name);
            // return old ID
            return Some(old_id);
        }
        return None;
    }

    pub fn record_append(&mut self, data: &[u8]) {
        self.recording_trace.extend_from_slice(data)
    }

    pub fn record_stop(&mut self, duration: u64, _enable_ddma: bool,
            _io: &Io, _ddma_mutex: &Mutex) -> Result<u32, SchedError> {
        let mut local_trace = Vec::new();
        let mut _remote_traces: BTreeMap<u8, Vec<u8>> = BTreeMap::new();

        if _enable_ddma && cfg!(has_drtio) {
            let mut trace = Vec::new();
            mem::swap(&mut self.recording_trace, &mut trace);
            trace.push(0);
            // analyze each entry and put in proper buckets, as the kernel core
            // sends whole chunks, to limit comms/kernel CPU communication,
            // and as only comms core has access to varios DMA buffers.
            let mut ptr = 0;
            while trace[ptr] != 0 {
                // ptr + 3 = tgt >> 24 (destination)
                let len = trace[ptr] as usize;
                let destination = trace[ptr+3];
                if destination == 0 {
                    local_trace.extend(&trace[ptr..ptr+len]);
                }
                else {
                    if let Some(remote_trace) = _remote_traces.get_mut(&destination) {
                        remote_trace.extend(&trace[ptr..ptr+len]);
                    } else {
                        _remote_traces.insert(destination, trace[ptr..ptr+len].to_vec());
                    }
                }
                // and jump to the next event
                ptr += len;
            }
        } else {
            // with disabled DDMA, move the whole trace to local
            mem::swap(&mut self.recording_trace, &mut local_trace);
        }

        local_trace.push(0);
        let data_len = local_trace.len();
        // Realign the local entry.
        local_trace.reserve(ALIGNMENT - 1);
        let padding = ALIGNMENT - local_trace.as_ptr() as usize % ALIGNMENT;
        let padding = if padding == ALIGNMENT { 0 } else { padding };
        for _ in 0..padding {
            // Vec guarantees that this will not reallocate
            local_trace.push(0)
        }
        for i in 1..data_len + 1 {
            local_trace[data_len + padding - i] = local_trace[data_len - i]
        }
        // trace ID is its pointer
        let id = local_trace[padding..].as_ptr() as u32;
        self.entries.insert(id, LocalEntry {
            trace: local_trace,
            padding_len: padding,
            duration: duration,
        });
        let mut name = String::new();
        mem::swap(&mut self.recording_name, &mut name);
        self.name_map.insert(name, id);

        #[cfg(has_drtio)]
        remote_dma::add_traces(_io, _ddma_mutex, id, _remote_traces)?;

        Ok(id)
    }

    pub fn erase(&mut self, name: &str) {
        if let Some(id) = self.name_map.get(name) {
            self.entries.remove(&id);
        }
        self.name_map.remove(name);
    }

    #[cfg(has_drtio)]
    pub fn get_id(&mut self, name: &str) -> Option<&u32> {
        self.name_map.get(name)
    }

    pub fn with_trace<F, R>(&self, name: &str, f: F) -> R
            where F: FnOnce(Option<&[u8]>, u64) -> R {
        if let Some(ptr) = self.name_map.get(name) {
            match self.entries.get(ptr) {
                Some(entry) => f(Some(&entry.trace[entry.padding_len..]), entry.duration),
                None => f(None, 0)
            }
        } else {
            f(None, 0)
        }
    }
}
