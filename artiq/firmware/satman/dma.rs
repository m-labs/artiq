use alloc::{vec::Vec, collections::btree_map::BTreeMap, string::String};
use core::mem;
use board_artiq::{drtioaux, drtio_routing::RoutingTable};
use board_misoc::{csr, cache::flush_l2_cache};
use proto_artiq::drtioaux_proto::PayloadStatus;
use routing::{Router, Sliceable};
use kernel::Manager as KernelManager;
use ::{cricon_select, cricon_read, RtioMaster, MASTER_PAYLOAD_MAX_SIZE};

const ALIGNMENT: usize = 64;

#[derive(PartialEq)]
enum ManagerState {
    Idle,
    Playback
}

pub struct RtioStatus {
    pub source: u8,
    pub id: u32, 
    pub error: u8,
    pub channel: u32, 
    pub timestamp: u64
}

#[derive(Debug)]
pub enum Error {
    IdNotFound,
    PlaybackInProgress,
    EntryNotComplete,
    MasterDmaFound,
    UploadFail,
}

struct Entry {
    trace: Vec<u8>,
    padding_len: usize,
    complete: bool,
    duration: u64, // relevant for locally ran DMA
}

impl Entry {
    pub fn from_vec(data: Vec<u8>, duration: u64) -> Entry {
        let mut entry = Entry {
            trace: data,
            padding_len: 0,
            complete: true,
            duration: duration,
        };
        entry.realign();
        entry
    }

    pub fn id(&self) -> u32 {
        self.trace[self.padding_len..].as_ptr() as u32
    }

    pub fn realign(&mut self) {
        self.trace.push(0);
        let data_len = self.trace.len();

        self.trace.reserve(ALIGNMENT - 1);
        let padding = ALIGNMENT - self.trace.as_ptr() as usize % ALIGNMENT;
        let padding = if padding == ALIGNMENT { 0 } else { padding };
        for _ in 0..padding {
            // Vec guarantees that this will not reallocate
            self.trace.push(0)
        }
        for i in 1..data_len + 1 {
            self.trace[data_len + padding - i] = self.trace[data_len - i]
        }
        self.complete = true;
        self.padding_len = padding;
    }
}

enum RemoteTraceState {
    Unsent,
    Sending(usize),
    Ready,
    Running(usize),
}

struct RemoteTraces {
    remote_traces: BTreeMap<u8, Sliceable>,
    state: RemoteTraceState,
}

impl RemoteTraces {
    pub fn new(traces: BTreeMap<u8, Sliceable>) -> RemoteTraces {
        RemoteTraces {
            remote_traces: traces,
            state: RemoteTraceState::Unsent
        }
    }

    // on subkernel request
    pub fn upload_traces(&mut self, id: u32, router: &mut Router, rank: u8, self_destination: u8, routing_table: &RoutingTable) -> usize {
        let len = self.remote_traces.len();
        if len > 0 {
            self.state = RemoteTraceState::Sending(self.remote_traces.len());
            for (dest, trace) in self.remote_traces.iter_mut() {
                // queue up the first packet for all destinations, rest will be sent after first ACK
                let mut data_slice: [u8; MASTER_PAYLOAD_MAX_SIZE] = [0; MASTER_PAYLOAD_MAX_SIZE];
                let meta = trace.get_slice_master(&mut data_slice);
                router.route(drtioaux::Packet::DmaAddTraceRequest {
                    source: self_destination, destination: *dest, id: id,
                    status: meta.status, length: meta.len, trace: data_slice
                }, routing_table, rank, self_destination);
            }
        }
        len
    }

    // on incoming Packet::DmaAddTraceReply
    pub fn ack_upload(&mut self, kernel_manager: &mut KernelManager, source: u8, id: u32, succeeded: bool, router: &mut Router, rank: u8, self_destination: u8, routing_table: &RoutingTable) {
        if let RemoteTraceState::Sending(count) = self.state {
            if let Some(trace) = self.remote_traces.get_mut(&source) {
                if trace.at_end() {
                        if count - 1 == 0 {
                            self.state = RemoteTraceState::Ready;
                            kernel_manager.ddma_remote_uploaded(succeeded);
                        } else {
                            self.state = RemoteTraceState::Sending(count - 1);
                        }
                } else {
                    // send next slice
                    let mut data_slice: [u8; MASTER_PAYLOAD_MAX_SIZE] = [0; MASTER_PAYLOAD_MAX_SIZE];
                    let meta = trace.get_slice_master(&mut data_slice);
                    router.route(drtioaux::Packet::DmaAddTraceRequest {
                        source: self_destination, destination: meta.destination, id: id,
                        status: meta.status, length: meta.len, trace: data_slice
                    }, routing_table, rank, self_destination);
                }
            }
        }
        
    }

    // on subkernel request
    pub fn playback(&mut self, id: u32, timestamp: u64, router: &mut Router, rank: u8, self_destination: u8, routing_table: &RoutingTable) {
        // route all the playback requests
        // remote traces + local trace
        self.state = RemoteTraceState::Running(self.remote_traces.len() + 1);
        for (dest, _) in self.remote_traces.iter() {
            router.route(drtioaux::Packet::DmaPlaybackRequest {
                source: self_destination, destination: *dest, id: id, timestamp: timestamp
            }, routing_table, rank, self_destination);
            // response will be ignored (succeeded = false handled by the main thread)
        }
    }

    // on incoming Packet::DmaPlaybackDone
    pub fn remote_finished(&mut self, kernel_manager: &mut KernelManager, error: u8, channel: u32, timestamp: u64) {
        if let RemoteTraceState::Running(count) = self.state {
            if error != 0 || count - 1 == 0 {
                // notify the kernel about a DDMA error or finish
                kernel_manager.ddma_finished(error, channel, timestamp);
                self.state = RemoteTraceState::Ready;
                // further messages will be ignored (if there was an error)
            } else { // no error and not the last one awaited
                self.state = RemoteTraceState::Running(count - 1);
            }
        }
    }

    pub fn erase(&mut self, id: u32, router: &mut Router, rank: u8, self_destination: u8, routing_table: &RoutingTable) {
        for (dest, _) in self.remote_traces.iter() {
            router.route(drtioaux::Packet::DmaRemoveTraceRequest { 
                source: self_destination, destination: *dest, id: id
            }, routing_table, rank, self_destination);
            // response will be ignored as this object will stop existing too
        }
    }
}

pub struct Manager {
    entries: BTreeMap<(u8, u32), Entry>,
    state: ManagerState,
    current_id: u32,
    current_source: u8,
    previous_cri_master: RtioMaster,

    remote_entries: BTreeMap<u32, RemoteTraces>,
    name_map: BTreeMap<String, u32>,
    recording_trace: Vec<u8>,
    recording_name: String
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
            current_id: 0,
            current_source: 0,
            previous_cri_master: RtioMaster::Drtio,
            state: ManagerState::Idle,
            remote_entries: BTreeMap::new(),
            name_map: BTreeMap::new(),
            recording_trace: Vec::new(),
            recording_name: String::new(),
        }
    }

    pub fn add(&mut self, source: u8, id: u32, status: PayloadStatus, trace: &[u8], trace_len: usize) -> Result<(), Error> {
        if status.is_first() {
            self.entries.remove(&(source, id));
        }
        let entry = match self.entries.get_mut(&(source, id)) {
            Some(entry) => {
                if entry.complete {
                    // replace entry
                    self.entries.remove(&(source, id));
                    self.entries.insert((source, id), Entry {
                        trace: Vec::new(),
                        padding_len: 0,
                        complete: false,
                        duration: 0
                    });
                    self.entries.get_mut(&(source, id)).unwrap()
                } else {
                    entry
                }
            },
            None => {
                self.entries.insert((source, id), Entry {
                    trace: Vec::new(),
                    padding_len: 0,
                    complete: false,
                    duration: 0,
                });
                self.entries.get_mut(&(source, id)).unwrap()
            },
        };
        entry.trace.extend(&trace[0..trace_len]);

        if status.is_last() {
            entry.realign();
            flush_l2_cache();
        }
        Ok(())
    }
    // API for subkernel
    pub fn record_start(&mut self, name: &str) {
        self.recording_name = String::from(name);
        self.recording_trace = Vec::new();
    }

    // API for subkernel
    pub fn record_append(&mut self, data: &[u8]) {
        self.recording_trace.extend_from_slice(data);
    }

    // API for subkernel
    pub fn record_stop(&mut self, duration: u64, self_destination: u8) -> Result<u32, Error> {
        let mut trace = Vec::new();
        mem::swap(&mut self.recording_trace, &mut trace);
        trace.push(0);
        let mut local_trace = Vec::new();
        let mut remote_traces: BTreeMap<u8, Sliceable> = BTreeMap::new();
        // analyze each entry and put in proper buckets, as the kernel core
        // sends whole chunks, to limit comms/kernel CPU communication,
        // and as only comms core has access to varios DMA buffers.
        let mut ptr = 0;
        while trace[ptr] != 0 {
            // ptr + 3 = tgt >> 24 (destination)
            let len = trace[ptr] as usize;
            let destination = trace[ptr+3];
            if destination == 0 {
                return Err(Error::MasterDmaFound);
            } else if destination == self_destination {
                local_trace.extend(&trace[ptr..ptr+len]);
            }
            else {
                if let Some(remote_trace) = remote_traces.get_mut(&destination) {
                    remote_trace.extend(&trace[ptr..ptr+len]);
                } else {
                    remote_traces.insert(destination, Sliceable::new(destination, trace[ptr..ptr+len].to_vec()));
                }
            }
            // and jump to the next event
            ptr += len;
        }
        let local_entry = Entry::from_vec(local_trace, duration);
        let id = local_entry.id();

        self.entries.insert((self_destination, id), local_entry);
        self.remote_entries.insert(id, RemoteTraces::new(remote_traces));
        let mut name = String::new();
        mem::swap(&mut self.recording_name, &mut name);
        self.name_map.insert(name, id);

        flush_l2_cache();

        Ok(id)
    }

    pub fn upload_traces(&mut self, id: u32, router: &mut Router, rank: u8, self_destination: u8,
            routing_table: &RoutingTable) -> Result<usize, Error> {
        let remote_traces = self.remote_entries.get_mut(&id);
        let mut len = 0;
        if let Some(traces) = remote_traces {
            len = traces.upload_traces(id, router, rank, self_destination, routing_table);
        }
        Ok(len)
    }

    pub fn with_trace<F, R>(&self, self_destination: u8, name: &str, f: F) -> R
        where F: FnOnce(Option<&[u8]>, u64) -> R {
        if let Some(ptr) = self.name_map.get(name) {
            match self.entries.get(&(self_destination, *ptr)) {
                Some(entry) => f(Some(&entry.trace[entry.padding_len..]), entry.duration),
                None => f(None, 0)
            }
        } else {
            f(None, 0)
        }
    }

    // API for subkernel
    pub fn playback_remote(&mut self, id: u32, timestamp: u64, 
        router: &mut Router, rank: u8, self_destination: u8, routing_table: &RoutingTable
    ) -> Result<(), Error> {
        if let Some(traces) = self.remote_entries.get_mut(&id) {
            traces.playback(id, timestamp, router, rank, self_destination, routing_table);
            Ok(())
        } else {
            Err(Error::IdNotFound)
        }
    }

    // API for subkernel
    pub fn erase_name(&mut self, name: &str, router: &mut Router, rank: u8, self_destination: u8, routing_table: &RoutingTable) {
        if let Some(id) = self.name_map.get(name) {
            if let Some(traces) = self.remote_entries.get_mut(&id) {
                traces.erase(*id, router, rank, self_destination, routing_table);
                self.remote_entries.remove(&id);
            }
            self.entries.remove(&(self_destination, *id));
            self.name_map.remove(name);
        }
    }

    // API for incoming DDMA (drtio)
    pub fn erase(&mut self, source: u8, id: u32) -> Result<(), Error> {
        match self.entries.remove(&(source, id)) {
            Some(_) => Ok(()),
            None => Err(Error::IdNotFound)
        }
    }

    pub fn remote_finished(&mut self, kernel_manager: &mut KernelManager, 
        id: u32, error: u8, channel: u32, timestamp: u64) {
        if let Some(entry) = self.remote_entries.get_mut(&id) {
            entry.remote_finished(kernel_manager, error, channel, timestamp);
        }
    }

    pub fn ack_upload(&mut self, kernel_manager: &mut KernelManager, source: u8, id: u32, succeeded: bool, 
        router: &mut Router, rank: u8, self_destination: u8, routing_table: &RoutingTable) {
            if let Some(entry) = self.remote_entries.get_mut(&id) {
                entry.ack_upload(kernel_manager, source, id, succeeded, router, rank, self_destination, routing_table);
            }
    }

    pub fn cleanup(&mut self, router: &mut Router, rank: u8, self_destination: u8, routing_table: &RoutingTable) {
        // after subkernel ends, remove all self-generated traces
        for (_, id) in self.name_map.iter_mut() {
            if let Some(traces) = self.remote_entries.get_mut(&id) {
                traces.erase(*id, router, rank, self_destination, routing_table);
                self.remote_entries.remove(&id);
            }
            self.entries.remove(&(self_destination, *id));
        }
        self.name_map.clear();
    }

    // API for both incoming DDMA (drtio) and subkernel
    pub fn playback(&mut self, source: u8, id: u32, timestamp: u64) -> Result<(), Error> {
        if self.state != ManagerState::Idle {
            return Err(Error::PlaybackInProgress);
        }

        let entry = match self.entries.get(&(source, id)){
            Some(entry) => entry,
            None => { return Err(Error::IdNotFound); }
        };
        if !entry.complete {
            return Err(Error::EntryNotComplete);
        }
        let ptr = entry.trace[entry.padding_len..].as_ptr();
        assert!(ptr as u32 % 64 == 0);

        self.state = ManagerState::Playback;
        self.current_id = id;
        self.current_source = source;
        self.previous_cri_master = cricon_read();

        unsafe {
            csr::rtio_dma::base_address_write(ptr as u64);
            csr::rtio_dma::time_offset_write(timestamp as u64);
    
            cricon_select(RtioMaster::Dma);
            csr::rtio_dma::enable_write(1);
            // playback has begun here, for status call check_state
        }
        Ok(())
    }

    pub fn get_status(&mut self) -> Option<RtioStatus> {
        if self.state != ManagerState::Playback {
            // nothing to report
            return None;
        }
        let dma_enable = unsafe { csr::rtio_dma::enable_read() };
        if dma_enable != 0 {
            return None;
        } else {
            self.state = ManagerState::Idle;
            unsafe { 
                cricon_select(self.previous_cri_master);
                let error = csr::rtio_dma::error_read();
                let channel = csr::rtio_dma::error_channel_read();
                let timestamp = csr::rtio_dma::error_timestamp_read();
                if error != 0 {
                    csr::rtio_dma::error_write(1);
                }
                return Some(RtioStatus {
                    source: self.current_source,
                    id: self.current_id,
                    error: error,
                    channel: channel, 
                    timestamp: timestamp });
            }
        }
    }

    pub fn running(&self) -> bool {
        self.state == ManagerState::Playback
    }

}