use core::mem;
use alloc::{vec::Vec, string::String, collections::btree_map::BTreeMap};

const ALIGNMENT: usize = 64;

#[derive(Debug)]
struct Entry {
    local_trace: Vec<u8>,
    local_padding_len: usize,
    duration: u64,
    remote_traces: BTreeMap<u8, Vec<u8>>
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
