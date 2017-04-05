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

    pub fn record_append(&mut self, timestamp: u64, channel: u32,
                         address: u32, data: &[u32]) {
        let writer = &mut self.recording;
        // See gateware/rtio/dma.py.
        let length = /*length*/1 + /*channel*/3 + /*timestamp*/8 + /*address*/2 +
                     /*data*/data.len() * 4;
        writer.write_all(&[
            (length    >>  0) as u8,
            (channel   >>  0) as u8,
            (channel   >>  8) as u8,
            (channel   >> 16) as u8,
            (timestamp >>  0) as u8,
            (timestamp >>  8) as u8,
            (timestamp >> 16) as u8,
            (timestamp >> 24) as u8,
            (timestamp >> 32) as u8,
            (timestamp >> 40) as u8,
            (timestamp >> 48) as u8,
            (timestamp >> 56) as u8,
            (address   >>  0) as u8,
            (address   >>  8) as u8,
        ]).unwrap();
        for &word in data {
            writer.write_all(&[
                (word >>  0) as u8,
                (word >>  8) as u8,
                (word >> 16) as u8,
                (word >> 24) as u8,
            ]).unwrap();
        }
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
