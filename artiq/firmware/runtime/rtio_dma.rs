use std::mem;
use std::vec::Vec;
use std::string::String;
use std::btree_map::BTreeMap;
use std::io::Write;

const ALIGNMENT: usize = 64;

#[derive(Debug)]
struct Entry {
    data: Vec<u8>,
    padding: usize,
    duration: u64
}

#[derive(Debug)]
pub struct Manager {
    entries: BTreeMap<String, Entry>,
    recording: Vec<u8>
}

impl Manager {
    pub fn new() -> Manager {
        Manager {
            entries: BTreeMap::new(),
            recording: Vec::new()
        }
    }

    pub fn record_start(&mut self) {
        self.recording = Vec::new();
    }

    pub fn record_append(&mut self, data: &[u8]) {
        self.recording.write_all(data).unwrap();
    }

    pub fn record_stop(&mut self, name: &str, duration: u64) {
        let mut recorded = Vec::new();
        mem::swap(&mut self.recording, &mut recorded);
        recorded.push(0);
        let data_len = recorded.len();

        // Realign.
        recorded.reserve(ALIGNMENT - 1);
        let padding = ALIGNMENT - recorded.as_ptr() as usize % ALIGNMENT;
        let padding = if padding == ALIGNMENT { 0 } else { padding };
        for _ in 0..padding {
            // Vec guarantees that this will not reallocate
            recorded.push(0)
        }
        for i in 1..data_len + 1 {
            recorded[data_len + padding - i] = recorded[data_len - i]
        }

        self.entries.insert(String::from(name), Entry {
            data: recorded,
            padding: padding,
            duration: duration
        });
    }

    pub fn erase(&mut self, name: &str) {
        self.entries.remove(name);
    }

    pub fn with_trace<F, R>(&self, name: &str, f: F) -> R
            where F: FnOnce(Option<&[u8]>, u64) -> R {
        match self.entries.get(name) {
            Some(entry) => f(Some(&entry.data[entry.padding..]), entry.duration),
            None => f(None, 0)
        }
    }
}
