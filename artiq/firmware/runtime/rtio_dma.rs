use core::mem;
use alloc::{vec::Vec, string::String, collections::btree_map::BTreeMap};

const ALIGNMENT: usize = 64;

static mut ID_COUNTER: u32 = 0;

#[derive(Debug)]
enum RemoteState {
    NotLoaded,
    Loaded,
    Running
}

#[derive(Debug)]
struct RemoteTrace {
    trace: Vec<u8>,
    state: RemoteState
}

impl RemoteTrace {
    pub fn new(initial_slice: &[u8]) -> RemoteTrace {
        RemoteTrace {
            trace: initial_slice.to_vec(),
            state: NotLoaded
        }
    }
}

#[derive(Debug)]
struct Entry {
    local_trace: Vec<u8>,
    local_padding_len: usize,
    duration: u64,
    remote_traces: BTreeMap<u8, SatTraceState>
}

#[derive(Debug)]
pub struct Manager {
    entries: BTreeMap<u32, Entry>,
    name_map: BTreeMap<String, u32>
    recording_trace: Vec<u8>,
    recording_id: u32
}

impl Manager {
    pub fn new() -> Manager {
        Manager {
            entries: BTreeMap::new(),
            name_map: BTreeMap::new(),
            recording_trace: Vec::new(),
            recording_id: 0
        }
    }

    pub fn record_start(&mut self, name: &str) {
        let recording_name = String::from(name);
        if let Some(id) = self.name_map.get(&recording_name) {
            // replacing a trace
            self.entries.remove(id);
            self.recording_id = id;
        } else {
            self.recording_id = ID_COUNTER;
            unsafe { ID_COUNTER += 1; }
            self.name_map.insert(recording_name, id);
        }
        self.recording_trace = Vec::new();
    }

    pub fn record_append(&mut self, data: &[u8]) {
        self.recording_trace.extend_from_slice(data)
    }

    pub fn record_stop(&mut self, duration: u64) {
        let mut trace = Vec::new();
        mem::swap(&mut self.recording_trace, &mut trace);
        trace.push(0);

        let id = self.recording_id;
        let local_trace = Vec::new();
        let remote_traces: BTreeMap<u8, SatTraceState> = BTreeMap::new();

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
                    remote_trace.trace.extend(trace[ptr..ptr+len]);
                } else {
                    remote_traces.insert(RemoteTrace::new(trace[ptr..ptr+len]));
                }
            }
            // and jump to the next event
            ptr += len;
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
        self.entries.insert(id, Entry {
            local_trace: local_trace,
            local_padding_len: padding,
            duration: duration,
            remote_traces: remote_traces
        });

    }

    pub fn erase(&mut self, name: &str) {
        if let Some(id) = self.name_map.get(name) {
            self.entries.remove(&id);
        }
        self.name_map.remove(name);
    }

    pub fn with_trace<F, R>(&self, name: &str, f: F) -> R
            where F: FnOnce(Option<&[u8]>, u64, u32) -> R {
        if let Some(id) = self.name_map.get(name) {
            match self.entries.get(id) {
                Some(entry) => f(Some(&entry.local_trace[entry.local_padding_len..]), entry.duration, id),
                None => f(None, 0, 0)
            }
        } else {
            f(None, 0, 0)
        }
    }
}
