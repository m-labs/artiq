use core::str;
use board_misoc::csr;
use alloc::{vec::Vec, collections::btree_map::BTreeMap};

const ALIGNMENT: usize = 64;

#[derive(Debug)]
struct Entry {
    trace: Vec<u8>,
    padding_len: usize,
    complete: bool
}

#[derive(Debug)]
pub struct Manager {
    entries: BTreeMap<u32, Entry>,
}

impl Manager {
    pub fn new() -> Manager {
        Manager {
            entries: BTreeMap::new(),
        }
    }

    pub fn add(&mut self, id: u32, last: bool, trace: &[u8], trace_len: usize) -> Result<(), &'static str> {
        let entry = match self.entries.get_mut(&id) {
            Some(entry) => entry,
            None => {
                self.entries.insert(id, Entry {
                    trace: Vec::new(),
                    padding_len: 0,
                    complete: false });
                self.entries.get_mut(&id).unwrap()
            },
        };
        entry.trace.extend(&trace[0..trace_len]);

        if last {
            entry.trace.push(0);
            let data_len = entry.trace.len();
    
            // Realign.
            entry.trace.reserve(ALIGNMENT - 1);
            let padding = ALIGNMENT - entry.trace.as_ptr() as usize % ALIGNMENT;
            let padding = if padding == ALIGNMENT { 0 } else { padding };
            for _ in 0..padding {
                // Vec guarantees that this will not reallocate
                entry.trace.push(0)
            }
            for i in 1..data_len + 1 {
                entry.trace[data_len + padding - i] = entry.trace[data_len - i]
            }
            entry.complete = true;
            entry.padding_len = padding;
        }
        Ok(())
    }

    pub fn erase(&mut self, id: u32) -> Result<(), &'static str> {
        match self.entries.remove(&id) {
            Some(_) => Ok(()),
            None => Err("Item did not exist")
        }
    }

    pub fn playback(&mut self, id: u32, timestamp: u64) -> Result<(), &'static str> {
        let entry = match self.entries.get(&id){
            Some(entry) => entry,
            None => { return Err("Entry for given ID not found"); }
        };
        let ptr = entry.trace.as_ptr();
        assert!(ptr as u32 % 64 == 0);

        unsafe {
            csr::rtio_dma::base_address_write(ptr as u64);
            csr::rtio_dma::time_offset_write(timestamp as u64);
    
            csr::cri_con::selected_write(1);
            csr::rtio_dma::enable_write(1);
            while csr::rtio_dma::enable_read() != 0 {}
            csr::cri_con::selected_write(0);
    
            let error = csr::rtio_dma::error_read();
            if error != 0 {
                csr::rtio_dma::error_write(1);
                if error & 1 != 0 {
                    return Err("RTIO underflow");
                }
                if error & 2 != 0 {
                    return Err("RTIO destination unreachable");
                }
            }
        }
        Ok(())
    }

}