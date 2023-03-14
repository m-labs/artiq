use core::mem;
use alloc::{vec::Vec, string::String, collections::btree_map::BTreeMap};
use sched::{Mutex, Io}
const ALIGNMENT: usize = 64;


#[derive(Debug)]
pub enum RemoteState {
    NotLoaded,
    Loaded,
    Running,
    PlaybackEnded { error: u32, channel: u32, timestamp: u64 }
}

#[derive(Debug)]
struct RemoteTrace {
    trace: Vec<u8>,
    state: RemoteState
}

impl From<Vec<u8>> for RemoteTrace {
    fn from(trace: Vec<u8>) -> Self {
        DmaRemoteTrace {
            trace: trace,
            state: NotLoaded
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
struct RemoteManager {
    mutex: Mutex;
    traces: BTreeMap<u32, BTreeMap<u8, RemoteTrace>>;
}

impl RemoteManager {
    pub fn new() -> RemoteManager {
        mutex: Muxex::new(), // probably unnecessary
        traces: BTreeMap::new()
    }

    pub fn add_traces(&mut self, id: u32, traces: BTreeMap<u8, Vec<u8>>) {
        let trace_map: BTreeMap<u8, RemoteTrace> = BTreeMap::new();
        for (destination, trace) in remote_traces {
            trace_map.insert(destination, trace.into());
        }
        self.traces.insert(id, trace_map);
    }

    pub fn get_traces(&mut self, id: u32) -> Option<BTreeMap<u8, RemoteTrace>> {
        self.traces.get(&id)?
    }

    pub fn change_state(&mut self, id: u32, destination: u8, new_state: RemoteState) {
        // for updating when handled by DRTIO
        if let Some(traces) = self.traces.get_mut(&id) {
            if let Some(remote_trace) = traces.get_mut(&destination) {
                remote_trace.change_state(new_state);
            }
        }
    }

    pub fn get_state(&mut self, id: u32, destination: u8) -> Option<&RemoteState> {
        Some(self.traces.get(&id)?.get(&destination)?.state)
    }

    pub fn await_done(&mut self, io: &Io, id: u32) -> RemoteState {
        // for waiting until all remote DMAs are finished
        // TODO
    }

    pub fn erase(&mut self, id: u32) {
        // erase the data - make sure you order satellites to remove first
        self.traces.remove(id);
    }

    pub fn get_destinations(&mut self, id: u32) -> Option<Vec<u8>> {
        // get a vector of destinations that need to be erased or triggered
        Some(self.traces.get(&id)?.keys().cloned().collect())
    }
}


#[derive(Debug)]
struct Entry {
    local_trace: Vec<u8>,
    local_padding_len: usize,
    duration: u64,
    remote_traces: BTreeMap<u8, Vec<u8>> // todo move it out of here, add to remote manager (and as argument for record_stop)
}

#[derive(Debug)]
pub struct Manager {
    entries: BTreeMap<u32, Entry>,
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
        }
    }

    pub fn record_start(&mut self, name: &str) {
        self.recording_name = String::from(name);
        if let Some(id) = self.name_map.get(&self.recording_name) {
            // replacing a trace
            self.entries.remove(id);
            self.name_map.remove(self.recording_name);
        }
        self.recording_trace = Vec::new();
    }

    pub fn record_append(&mut self, data: &[u8]) {
        self.recording_trace.extend_from_slice(data)
    }

    pub fn record_stop(&mut self, duration: u64, disable_ddma: bool) -> u32 {
        let mut local_trace = Vec::new();
        let remote_traces: BTreeMap<u8, SatTraceState> = BTreeMap::new();

        if !disable_ddma {
            let mut trace = Vec::new();
            mem::swap(&mut self.recording_trace, &mut trace);
            trace.push(0);
            // analyze each entry and put in proper buckets
            let mut ptr = 0;
            while trace[ptr] != 0 {
                // ptr + 3 = tgt >> 24 (destination)
                let len = trace[ptr];
                let destination = trace[ptr+3];
                if destination == 0 {
                    local_trace.extend(trace[ptr..ptr+len]);
                }
                else {
                    if let Some(remote_trace) = remote_traces.get_mut(&destination) {
                        remote_trace.extend(trace[ptr..ptr+len]);
                    } else {
                        remote_traces.insert(trace[ptr..ptr+len].to_vec());
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
        self.entries.insert(id, Entry {
            local_trace: local_trace,
            local_padding_len: padding,
            duration: duration,
            remote_traces: remote_traces
        });
        self.name_map.insert(self.recording_name, id);
        id
    }

    pub fn get_remotes(&mut self, id: u32) -> Option<BTreeMap<u8, Vec<u8>>>{
        self.entries.get_mut(&id)
    }

    pub fn erase(&mut self, name: &str) {
        if let Some(id) = self.name_map.get(name) {
            self.entries.remove(&id);
        }
        self.name_map.remove(name);
    }

    pub fn with_trace<F, R>(&self, name: &str, f: F) -> R
            where F: FnOnce(Option<&[u8]>, u64) -> R {
        if let Some(ptr) = self.name_map.get(name) {
            match self.entries.get(ptr) {
                Some(entry) => f(Some(&entry.local_trace[entry.local_padding_len..]), entry.duration),
                None => f(None, 0)
            }
        } else {
            f(None, 0)
        }
    }
}
