use board_misoc::csr;
use alloc::{vec::Vec, collections::btree_map::BTreeMap};

const ALIGNMENT: usize = 64;

#[derive(Debug, PartialEq)]
enum ManagerState {
    Idle,
    Playback
}

pub struct RtioStatus {
    pub id: u32, 
    pub error: u8, 
    pub channel: u32, 
    pub timestamp: u64
}

pub enum Error {
    IdNotFound,
    PlaybackInProgress,
    EntryNotComplete
}

#[derive(Debug)]
struct Entry {
    trace: Vec<u8>,
    complete: bool
}

#[derive(Debug)]
pub struct Manager {
    entries: BTreeMap<u32, Entry>,
    state: ManagerState,
    currentid: u32
}

impl Manager {
    pub fn new() -> Manager {
        // in case Manager is created during a DMA in progress
        // wait for it to end
        unsafe {
            while csr::rtio_dma::enable_read() != 0 {} 
        }
        Manager {
            entries: BTreeMap::new(),
            currentid: 0,
            state: ManagerState::Idle,
        }
    }

    pub fn add(&mut self, id: u32, last: bool, trace: &[u8], trace_len: usize) -> Result<(), Error> {
        let entry = match self.entries.get_mut(&id) {
            Some(entry) => entry,
            None => {
                self.entries.insert(id, Entry {
                    trace: Vec::new(),
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
        }
        Ok(())
    }

    pub fn erase(&mut self, id: u32) -> Result<(), Error> {
        match self.entries.remove(&id) {
            Some(_) => Ok(()),
            None => Err(Error::IdNotFound)
        }
    }

    pub fn playback(&mut self, id: u32, timestamp: u64) -> Result<(), Error> {
        if self.state != ManagerState::Idle {
            return Err(Error::PlaybackInProgress);
        }

        let entry = match self.entries.get(&id){
            Some(entry) => entry,
            None => { return Err(Error::IdNotFound); }
        };
        if !entry.complete {
            return Err(Error::EntryNotComplete);
        }
        let ptr = entry.trace.as_ptr();
        assert!(ptr as u32 % 64 == 0);

        self.state = ManagerState::Playback;
        self.currentid = id;

        unsafe {
            csr::rtio_dma::base_address_write(ptr as u64);
            csr::rtio_dma::time_offset_write(timestamp as u64);
    
            csr::cri_con::selected_write(1);
            csr::rtio_dma::enable_write(1);
            // playback has begun here, for status call check_state
        }
        Ok(())
    }

    pub fn check_state(&mut self) -> Option<RtioStatus> {
        if self.state != ManagerState::Playback {
            // nothing to report
            return None;
        }
        let dma_enable = unsafe { csr::rtio_dma::enable_read() };
        if dma_enable != 0 {
            return None;
        }
        else {
            self.state = ManagerState::Idle;
            unsafe { 
                csr::cri_con::selected_write(0);
                let error =  csr::rtio_dma::error_read();
                let channel = csr::rtio_dma::error_channel_read();
                let timestamp = csr::rtio_dma::error_timestamp_read();
                if error != 0 {
                    csr::rtio_dma::error_write(1);
                }
                return Some(RtioStatus { 
                    id: self.currentid, 
                    error: error,
                    channel: channel, 
                    timestamp: timestamp });
            }
        }
    }

}