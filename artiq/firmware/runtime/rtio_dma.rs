use core::mem;
use alloc::{Vec, String, BTreeMap};

const ALIGNMENT: usize = 64;

#[derive(Debug)]
struct Entry {
    trace: Vec<u8>,
    padding_len: usize,
    duration: u64
}

#[derive(Debug)]
pub struct Manager {
    entries: BTreeMap<String, Entry>,
    recording_name: String,
    recording_trace: Vec<u8>
}

impl Manager {
    pub fn new() -> Manager {
        Manager {
            entries: BTreeMap::new(),
            recording_name: String::new(),
            recording_trace: Vec::new(),
        }
    }

    pub fn record_start(&mut self, name: &str) {
        self.recording_name = String::from(name);
        self.recording_trace = Vec::new();

        // or we could needlessly OOM replacing a large trace
        self.entries.remove(name);
    }

    pub fn record_append(&mut self, data: &[u8]) {
        self.recording_trace.extend_from_slice(data)
    }

    pub fn record_stop(&mut self, duration: u64) {
        let mut trace = Vec::new();
        mem::swap(&mut self.recording_trace, &mut trace);
        trace.push(0);
        let data_len = trace.len();

        // Realign.
        trace.reserve(ALIGNMENT - 1);
        let padding = ALIGNMENT - trace.as_ptr() as usize % ALIGNMENT;
        let padding = if padding == ALIGNMENT { 0 } else { padding };
        for _ in 0..padding {
            // Vec guarantees that this will not reallocate
            trace.push(0)
        }
        for i in 1..data_len + 1 {
            trace[data_len + padding - i] = trace[data_len - i]
        }

        let mut name = String::new();
        mem::swap(&mut self.recording_name, &mut name);
        self.entries.insert(name, Entry {
            trace: trace,
            padding_len: padding,
            duration: duration
        });
    }

    pub fn erase(&mut self, name: &str) {
        self.entries.remove(name);
    }

    pub fn with_trace<F, R>(&self, name: &str, f: F) -> R
            where F: FnOnce(Option<&[u8]>, u64) -> R {
        match self.entries.get(name) {
            Some(entry) => f(Some(&entry.trace[entry.padding_len..]), entry.duration),
            None => f(None, 0)
        }
    }
}
