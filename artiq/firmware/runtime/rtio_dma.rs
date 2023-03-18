use core::mem;
use alloc::{vec::Vec, string::String, collections::btree_map::BTreeMap};
use sched::Io;
use board_misoc::clock;
const ALIGNMENT: usize = 64;


#[derive(Debug, PartialEq, Clone)]
pub enum RemoteState {
    NotLoaded,
    Loaded,
    Running,
    PlaybackEnded { error: u8, channel: u32, timestamp: u64 }
}

#[derive(Debug)]
struct RemoteTrace {
    trace: Vec<u8>,
    state: RemoteState
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

    pub fn update_state(&mut self, new_state: RemoteState) {
        self.state = new_state;
    }

    pub fn get_state(&self) -> &RemoteState {
        &self.state
    }
}


#[derive(Debug)]
pub struct RemoteManager {
    traces: BTreeMap<u32, BTreeMap<u8, RemoteTrace>>
}

impl RemoteManager {
    pub fn new() -> RemoteManager {
        RemoteManager {
            traces: BTreeMap::new()
        }
    }

    pub fn add_traces(&mut self, id: u32, traces: BTreeMap<u8, Vec<u8>>) {
        let mut trace_map: BTreeMap<u8, RemoteTrace> = BTreeMap::new();
        for (destination, trace) in traces {
            trace_map.insert(destination, trace.into());
        }
        self.traces.insert(id, trace_map);
    }

    pub fn get_traces(&mut self, id: u32) -> Option<&mut BTreeMap<u8, RemoteTrace>> {
        self.traces.get_mut(&id)
    }

    pub fn get_traces_for_destination(&mut self, destination: u8) -> BTreeMap<u32, &RemoteTrace> {
        // get all traces for given destination
        let mut dest_traces: BTreeMap<u32, &RemoteTrace> = BTreeMap::new();
        for (id, traces) in self.traces {
            if let Some(dest_trace) = traces.get(&destination) {
                dest_traces.insert(id.clone(), dest_trace);
            }
        }
        dest_traces
    }

    pub fn change_state(&mut self, id: u32, destination: u8, new_state: RemoteState) {
        // for updating when handled by DRTIO
        if let Some(traces) = self.traces.get_mut(&id) {
            if let Some(remote_trace) = traces.get_mut(&destination) {
                remote_trace.update_state(new_state);
            }
        }
    }

    pub fn get_state(&mut self, id: u32, destination: u8) -> Option<&RemoteState> {
        Some(&self.traces.get(&id)?.get(&destination)?.state)
    }

    pub fn await_done(&mut self, io: &Io, id: u32, timeout: u64) -> Result<RemoteState, &'static str> {
        let max_time = clock::get_ms() + timeout as u64;
        io.until(|| {
            while clock::get_ms() < max_time {
                if let Some(traces) = self.traces.get(&id) {
                    for (_dest, trace) in traces {
                        match trace.get_state() {
                            RemoteState::PlaybackEnded {error: _, channel: _, timestamp: _} => (),
                            _ => return false
                        }
                    }
                }
            }
            true
        }).unwrap();
        if clock::get_ms() > max_time {
            return Err("Timed out waiting for results.");
        }
        // clear the internal state, if there have been any errors, return one of them
        let mut playback_state: RemoteState = RemoteState::PlaybackEnded { error: 0, channel: 0, timestamp: 0 };
        if let Some(traces) = self.traces.get_mut(&id) {
            for (_dest, trace) in traces {
                let state = trace.get_state();
                match state {
                    RemoteState::PlaybackEnded {error: e, channel: _c, timestamp: _ts} => if *e != 0 { playback_state = state.clone(); },
                    _ => (),
                }
                trace.update_state(RemoteState::Loaded);
            }
        }
        return Ok(playback_state);

    }

    pub fn erase(&mut self, id: &u32) {
        // erase the data - make sure you order satellites to remove first
        self.traces.remove(id);
    }

    pub fn get_destinations(&mut self, id: u32) -> Option<Vec<u8>> {
        // get a vector of destinations that need to be erased or triggered
        Some(self.traces.get(&id)?.keys().cloned().collect())
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

    pub fn record_start(&mut self, name: &str) {
        self.recording_name = String::from(name);
        if let Some(id) = self.name_map.get(&self.recording_name) {
            // replacing a trace
            self.entries.remove(&id);
            self.name_map.remove(&self.recording_name);
        }
        self.recording_trace = Vec::new();
    }

    pub fn record_append(&mut self, data: &[u8]) {
        self.recording_trace.extend_from_slice(data)
    }

    pub fn record_stop(&mut self, duration: u64, enable_ddma: bool) -> (u32, BTreeMap<u8, Vec<u8>>) {
        let mut local_trace = Vec::new();
        let mut remote_traces: BTreeMap<u8, Vec<u8>> = BTreeMap::new();

        if enable_ddma {
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
                    if let Some(remote_trace) = remote_traces.get_mut(&destination) {
                        remote_trace.extend(&trace[ptr..ptr+len]);
                    } else {
                        remote_traces.insert(destination, trace[ptr..ptr+len].to_vec());
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
        (id, remote_traces)
    }

    pub fn erase(&mut self, name: &str) {
        if let Some(id) = self.name_map.get(name) {
            self.entries.remove(&id);
        }
        self.name_map.remove(name);
    }

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
