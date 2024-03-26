use core::{mem, option::NoneError};
use alloc::{string::String, format, vec::Vec, collections::btree_map::BTreeMap};
use cslice::AsCSlice;

use board_artiq::{drtioaux, mailbox, spi};
use board_misoc::{csr, clock, i2c};
use proto_artiq::{
    drtioaux_proto::PayloadStatus,
    kernel_proto as kern, 
    session_proto::Reply::KernelException as HostKernelException, 
    rpc_proto as rpc};
use eh::eh_artiq;
use io::Cursor;
use kernel::eh_artiq::StackPointerBacktrace;

use ::{cricon_select, RtioMaster};
use cache::Cache;
use dma::{Manager as DmaManager, Error as DmaError};
use aux::{AuxManager, Sliceable, SliceMeta, Error as AuxError};
use SAT_PAYLOAD_MAX_SIZE;
use MASTER_PAYLOAD_MAX_SIZE;

mod kernel_cpu {
    use super::*;
    use core::ptr;

    use proto_artiq::kernel_proto::{KERNELCPU_EXEC_ADDRESS, KERNELCPU_LAST_ADDRESS, KSUPPORT_HEADER_SIZE};

    pub unsafe fn start() {
        if csr::kernel_cpu::reset_read() == 0 {
            panic!("attempted to start kernel CPU when it is already running")
        }

        stop();

        extern {
            static _binary____ksupport_ksupport_elf_start: u8;
            static _binary____ksupport_ksupport_elf_end: u8;
        }
        let ksupport_start = &_binary____ksupport_ksupport_elf_start as *const _;
        let ksupport_end   = &_binary____ksupport_ksupport_elf_end as *const _;
        ptr::copy_nonoverlapping(ksupport_start,
                                (KERNELCPU_EXEC_ADDRESS - KSUPPORT_HEADER_SIZE) as *mut u8,
                                ksupport_end as usize - ksupport_start as usize);

        csr::kernel_cpu::reset_write(0);
    }

    pub unsafe fn stop() {
        csr::kernel_cpu::reset_write(1);
        cricon_select(RtioMaster::Drtio);

        mailbox::acknowledge();
    }

    pub fn validate(ptr: usize) -> bool {
        ptr >= KERNELCPU_EXEC_ADDRESS && ptr <= KERNELCPU_LAST_ADDRESS
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum KernelState {
    Absent,
    Loaded,
    Running,
    MsgAwait { id: u32, max_time: i64, tags: Vec<u8> },
    MsgSending { transaction_id: u8 },
    SubkernelAwaitLoad { transaction_id: u8 },
    SubkernelAwaitFinish { max_time: i64, id: u32 },
    DmaUploading { id: u32, max_time: u64 },
    DmaAwait { id: u32, max_time: u64 },
}

#[derive(Debug)]
pub enum Error {
    Load(String),
    KernelNotFound,
    InvalidPointer(usize),
    Unexpected(String),
    NoMessage,
    AwaitingMessage,
    SubkernelIoError,
    DrtioError,
    KernelException(Sliceable),
    DmaError(DmaError),
}

impl From<NoneError> for Error {
    fn from(_: NoneError) -> Error {
        Error::KernelNotFound
    }
}

impl From<io::Error<!>> for Error {
    fn from(_value: io::Error<!>) -> Error {
        Error::SubkernelIoError
    }
}

impl From<drtioaux::Error<!>> for Error {
    fn from(_value: drtioaux::Error<!>) -> Error {
        Error::DrtioError
    }
}

impl From<AuxError> for Error {
    fn from(_value: AuxError) -> Error {
        Error::DrtioError
    }
}

impl From<DmaError> for Error {
    fn from(value: DmaError) -> Error {
        Error::DmaError(value)
    }
}

macro_rules! unexpected {
    ($($arg:tt)*) => (return Err(Error::Unexpected(format!($($arg)*))));
}

/* represents interkernel messages */
struct Message {
    id: u32,
    count: u8,
    data: Vec<u8>
}

#[derive(PartialEq)]
enum OutMessageState {
    NoMessage,
    MessageBeingSent,
    MessageSent
}

/* for dealing with incoming and outgoing interkernel messages */
struct MessageManager {
    out_message: Option<Sliceable>,
    out_state: OutMessageState,
    in_queue: Vec<Message>,
    in_buffer: Option<Message>,
}

// Per-run state
struct Session {
    kernel_state: KernelState,
    log_buffer: String,
    last_exception: Option<Sliceable>,
    source: u8, // which destination requested running the kernel
    messages: MessageManager,
    subkernels_finished: Vec<u32> // ids of subkernels finished
}

#[derive(Debug)]
struct KernelLibrary {
    library: Vec<u8>,
    complete: bool
}

pub struct Manager {
    kernels: BTreeMap<u32, KernelLibrary>,
    current_id: u32,
    session: Session,
    cache: Cache,
    last_finished: Option<SubkernelFinished>
}

pub struct SubkernelFinished {
    pub id: u32,
    pub with_exception: bool,
    pub exception_source: u8,
    pub source: u8
}

impl MessageManager {
    pub fn new() -> MessageManager {
        MessageManager {
            out_message: None,
            out_state: OutMessageState::NoMessage,
            in_queue: Vec::new(),
            in_buffer: None
        }
    }

    pub fn handle_incoming(&mut self, status: PayloadStatus, length: usize, id: u32, data: &[u8; MASTER_PAYLOAD_MAX_SIZE]) {
        // called when receiving a message from master
        if status.is_first() {
            // clear the buffer for first message
            self.in_buffer = None;
        }
        match self.in_buffer.as_mut() {
            Some(message) => message.data.extend(&data[..length]),
            None => {
                self.in_buffer = Some(Message {
                    id: id,
                    count: data[0],
                    data: data[1..length].to_vec()
                });
            }
        };
        if status.is_last() {
            // when done, remove from working queue
            self.in_queue.push(self.in_buffer.take().unwrap());
        }
    }

    pub fn get_outgoing_slice(&mut self, data_slice: &mut [u8; MASTER_PAYLOAD_MAX_SIZE]) -> Option<SliceMeta> {
        if self.out_state != OutMessageState::MessageBeingSent {
            return None;
        }
        let meta = self.out_message.as_mut()?.get_slice_master(data_slice);
        if meta.status.is_last() {
            // clear the message slot
            self.out_message = None;
            // notify kernel with a flag that message is sent
            self.out_state = OutMessageState::MessageSent;
        }
        Some(meta)
    }

    pub fn ack_slice(&mut self) -> bool {
        // returns whether or not there's more to be sent
        match self.out_state {
            OutMessageState::MessageBeingSent => true,
            OutMessageState::MessageSent => {
                self.out_state = OutMessageState::NoMessage;
                false
            },
            _ => { 
                warn!("received unsolicited SubkernelMessageAck"); 
                false 
            }
        }
    }

    pub fn accept_outgoing(&mut self, id: u32, destination: u8, 
        count: u8, tag: &[u8], data: *const *const (), aux_mgr: &mut AuxManager
    ) -> Result<u8, Error>  {
        let mut writer = Cursor::new(Vec::new());
        rpc::send_args(&mut writer, 0, tag, data, false)?;
        // skip service tag, but write the count
        let mut data = writer.into_inner().split_off(3);
        data[0] = count;
        self.out_message = Some(Sliceable::new(destination, data));

        let mut data_slice: [u8; MASTER_PAYLOAD_MAX_SIZE] = [0; MASTER_PAYLOAD_MAX_SIZE];
        self.out_state = OutMessageState::MessageBeingSent;
        let meta = self.get_outgoing_slice(&mut data_slice).unwrap();
        let transaction_id = aux_mgr.transact(destination, false, drtioaux::Payload::SubkernelMessage {
                id: id, status: meta.status, length: meta.len as u16, data: data_slice
        })?;
        Ok(transaction_id)
    }

    pub fn get_incoming(&mut self, id: u32) -> Option<Message> {
        for i in 0..self.in_queue.len() {
            if self.in_queue[i].id == id {
                return Some(self.in_queue.remove(i));
            }
        }
        None
    }

    pub fn pending_ids(&self) -> Vec<u32> {
        let mut pending_ids: Vec<u32> = Vec::new();
        for msg in self.in_queue.iter() {
            pending_ids.push(msg.id);
        }
        pending_ids
    }
}

impl Session {
    pub fn new() -> Session {
        Session {
            kernel_state: KernelState::Absent,
            log_buffer: String::new(),
            last_exception: None,
            source: 0,
            messages: MessageManager::new(),
            subkernels_finished: Vec::new()
        }
    }

    fn running(&self) -> bool {
        match self.kernel_state {
            KernelState::Absent | KernelState::Loaded  => false,
            _ => true
        }
    }

    fn flush_log_buffer(&mut self) {
        if &self.log_buffer[self.log_buffer.len() - 1..] == "\n" {
            for line in self.log_buffer.lines() {
                info!(target: "kernel", "{}", line);
            }
            self.log_buffer.clear()
        }
    }
}

impl Manager {
    pub fn new() -> Manager {
        Manager {
            kernels: BTreeMap::new(),
            current_id: 0,
            session: Session::new(),
            cache: Cache::new(),
            last_finished: None,
        }
    }

    pub fn add(&mut self, id: u32, status: PayloadStatus, data: &[u8], data_len: usize) -> Result<(), Error> {
        if status.is_first() {
            // in case master is interrupted, and subkernel is sent again, clean the state
            self.kernels.remove(&id);
        }
        let kernel = match self.kernels.get_mut(&id) {
            Some(kernel) => {
                if kernel.complete {
                    // replace entry
                    self.kernels.remove(&id);
                    self.kernels.insert(id, KernelLibrary {
                        library: Vec::new(),
                        complete: false });
                    self.kernels.get_mut(&id)?
                } else {
                    kernel
                }
            },
            None => {
                self.kernels.insert(id, KernelLibrary {
                    library: Vec::new(),
                    complete: false });
                self.kernels.get_mut(&id)?
            },
        };
        kernel.library.extend(&data[0..data_len]);

        kernel.complete = status.is_last();
        Ok(())
    }

    pub fn is_running(&self) -> bool {
        self.session.running()
    }

    pub fn stop(&mut self) {
        unsafe { kernel_cpu::stop() }
        self.session.kernel_state = KernelState::Absent;
        unsafe { self.cache.unborrow() }
    }

    pub fn run(&mut self, source: u8, id: u32) -> Result<(), Error> {
        info!("starting subkernel #{}", id);
        if self.session.kernel_state != KernelState::Loaded
            || self.current_id != id {
            self.load(id)?;
        }
        self.session.source = source;
        self.session.kernel_state = KernelState::Running;
        cricon_select(RtioMaster::Kernel);
    
        kern_acknowledge()
    }

    pub fn message_handle_incoming(&mut self, status: PayloadStatus, length: usize, id: u32, slice: &[u8; MASTER_PAYLOAD_MAX_SIZE]) {
        if !self.is_running() {
            return;
        }
        self.session.messages.handle_incoming(status, length, id, slice);
    }

    pub fn load(&mut self, id: u32) -> Result<(), Error> {
        if self.current_id == id && self.session.kernel_state == KernelState::Loaded {
            return Ok(())
        }
        if !self.kernels.get(&id)?.complete {
            return Err(Error::KernelNotFound)
        }
        self.current_id = id;
        self.session = Session::new();
        self.stop();
        
        unsafe { 
            kernel_cpu::start();

            kern_send(&kern::LoadRequest(&self.kernels.get(&id)?.library)).unwrap();
            kern_recv(|reply| {
                match reply {
                    kern::LoadReply(Ok(())) => {
                        self.session.kernel_state = KernelState::Loaded;
                        Ok(())
                    }
                    kern::LoadReply(Err(error)) => {
                        kernel_cpu::stop();
                        error!("load error: {:?}", error);
                        Err(Error::Load(format!("{}", error)))
                    }
                    other => {
                        unexpected!("unexpected kernel CPU reply to load request: {:?}", other)
                    }
                }
            })
        }
    }

    pub fn exception_get_slice(&mut self, data_slice: &mut [u8; SAT_PAYLOAD_MAX_SIZE]) -> SliceMeta {
        match self.session.last_exception.as_mut() {
            Some(exception) => exception.get_slice_sat(data_slice),
            None => SliceMeta { destination: 0, len: 0, status: PayloadStatus::FirstAndLast }
        }
    }

    fn runtime_exception(&mut self, cause: Error) {
        let raw_exception: Vec<u8> = Vec::new();
        let mut writer = Cursor::new(raw_exception);
        match (HostKernelException {
            exceptions: &[Some(eh_artiq::Exception {
                id:       11,  // SubkernelError, defined in ksupport
                message:  format!("in subkernel id {}: {:?}", self.current_id, cause).as_c_slice(),
                param:    [0, 0, 0],
                file:     file!().as_c_slice(),
                line:     line!(),
                column:   column!(),
                function: format!("subkernel id {}", self.current_id).as_c_slice(),
            })],
            stack_pointers: &[StackPointerBacktrace {
                stack_pointer: 0,
                initial_backtrace_size: 0,
                current_backtrace_size: 0
            }],
            backtrace: &[],
            async_errors: 0
        }).write_to(&mut writer) {
            Ok(_) => self.session.last_exception = Some(Sliceable::new(0, writer.into_inner())),
            Err(_) => error!("Error writing exception data")
        }
    }

    pub fn ddma_finished(&mut self, error: u8, channel: u32, timestamp: u64) {
        if let KernelState::DmaAwait { .. } = self.session.kernel_state {
            kern_send(&kern::DmaAwaitRemoteReply { 
                timeout: false, error: error, channel: channel, timestamp: timestamp 
            }).unwrap();
            self.session.kernel_state = KernelState::Running;
        }
    }

    pub fn process_kern_requests(&mut self, aux_mgr: &mut AuxManager, dma_mgr: &mut DmaManager) {
        macro_rules! finished {
            ($with_exception:expr) => {{ Some(SubkernelFinished { 
                source: self.session.source, id: self.current_id,
                with_exception: $with_exception, exception_source: aux_mgr.self_destination()
            }) }}
        }

        if let Some(subkernel_finished) = self.last_finished.take() {
            info!("subkernel {} finished, with exception: {}", subkernel_finished.id, subkernel_finished.with_exception);
            let pending = self.session.messages.pending_ids();
            if pending.len() > 0 {
                warn!("subkernel terminated with messages still pending: {:?}", pending);
            }
            aux_mgr.transact(subkernel_finished.source, false, drtioaux::Payload::SubkernelFinished {
                id: subkernel_finished.id, with_exception: subkernel_finished.with_exception,
                exception_src: subkernel_finished.exception_source
            }).unwrap();
            dma_mgr.cleanup(aux_mgr);
        }

        if !self.is_running() {
            return;
        }

        match self.process_external_messages(aux_mgr, dma_mgr) {
            Ok(()) => (),
            Err(Error::AwaitingMessage) => return, // kernel still waiting, do not process kernel messages
            Err(Error::KernelException(exception)) => {
                unsafe { kernel_cpu::stop() }
                self.session.kernel_state = KernelState::Absent;
                unsafe { self.cache.unborrow() }
                self.session.last_exception = Some(exception);
                self.last_finished = finished!(true);
            },
            Err(e) => { 
                error!("Error while running processing external messages: {:?}", e);
                self.stop();
                self.runtime_exception(e);
                self.last_finished = finished!(true);
             }
        }

        match self.process_kern_message(aux_mgr, dma_mgr) {
            Ok(Some(with_exception)) => {
                self.last_finished = finished!(with_exception)
            },
            Ok(None) | Err(Error::NoMessage) => (),
            Err(e) => { 
                error!("Error while running kernel: {:?}", e); 
                self.stop(); 
                self.runtime_exception(e);
                self.last_finished = finished!(true);
            }
        }
    }

    fn process_external_messages(&mut self, aux_mgr: &mut AuxManager, dma_mgr: &mut DmaManager) -> Result<(), Error> {
        match &self.session.kernel_state {
            KernelState::MsgAwait { id, max_time, tags } => {
                if *max_time > 0 && clock::get_ms() > *max_time as u64 {
                    kern_send(&kern::SubkernelMsgRecvReply { status: kern::SubkernelStatus::Timeout, count: 0 })?;
                    self.session.kernel_state = KernelState::Running;
                    return Ok(())
                }
                if let Some(message) = self.session.messages.get_incoming(*id) {
                    kern_send(&kern::SubkernelMsgRecvReply { status: kern::SubkernelStatus::NoError, count: message.count })?;
                    let tags = tags.clone();
                    self.session.kernel_state = KernelState::Running;
                    pass_message_to_kernel(&message, &tags)
                } else {
                    Err(Error::AwaitingMessage)
                }
            },
            KernelState::MsgSending { transaction_id } => {
                match aux_mgr.check_transaction(*transaction_id)? {
                    Some(drtioaux::Payload::PacketAck) => {
                        if self.session.messages.ack_slice() {
                            let mut data_slice: [u8; MASTER_PAYLOAD_MAX_SIZE] = [0; MASTER_PAYLOAD_MAX_SIZE];
                            if let Some(meta) = self.session.messages.get_outgoing_slice(&mut data_slice) {
                                let new_id = aux_mgr.transact(meta.destination, false, drtioaux::Payload::SubkernelMessage {
                                    id: self.current_id,
                                    status: meta.status, length: meta.len as u16, data: data_slice
                                })?;
                                self.session.kernel_state = KernelState::MsgSending { transaction_id: new_id };
                            }
                            Ok(())
                        } else {
                            // no more to send
                            self.session.kernel_state = KernelState::Running;
                            kern_acknowledge()
                        }
                    },
                    Some(p) => {
                        error!("subkernel message send received unexpected reply: {:?}", p);
                        Err(Error::DrtioError)
                    },
                    None => Err(Error::AwaitingMessage),
                }
            },
            KernelState::SubkernelAwaitFinish { max_time, id } => {
                if *max_time > 0 && clock::get_ms() > *max_time as u64 {
                    kern_send(&kern::SubkernelAwaitFinishReply { status: kern::SubkernelStatus::Timeout })?;
                    self.session.kernel_state = KernelState::Running;
                } else {
                    let mut i = 0;
                    for status in &self.session.subkernels_finished {
                        if *status == *id {
                            kern_send(&kern::SubkernelAwaitFinishReply { status: kern::SubkernelStatus::NoError })?;
                            self.session.kernel_state = KernelState::Running;
                            self.session.subkernels_finished.swap_remove(i);
                            break;
                        }
                        i += 1;
                    }
                }
                Ok(())
            }
            KernelState::DmaAwait { id, max_time } => {
                let res = dma_mgr.check_playbacks(*id, aux_mgr);
                if clock::get_ms() > *max_time || res.is_err() {
                    kern_send(&kern::DmaAwaitRemoteReply { timeout: true, error: 0, channel: 0, timestamp: 0 })?;
                    self.session.kernel_state = KernelState::Running;
                }
                // ddma_finished() and nack() covers the other case
                Ok(())
            }
            KernelState::DmaUploading { id, max_time } => {
                match dma_mgr.check_uploads(*id, aux_mgr) {
                    Ok(true) => {
                        self.session.kernel_state = KernelState::Running;
                        kern_acknowledge().unwrap();
                    }
                    Ok(false) => {
                        if clock::get_ms() > *max_time {
                            unexpected!("DMAError: Timed out sending traces to remote");
                        }
                    }
                    Err(_) => {
                        self.stop();
                        self.runtime_exception(Error::DmaError(DmaError::UploadFail));
                    }
                };
                Ok(())
            }
            KernelState::SubkernelAwaitLoad { transaction_id } => {
                match aux_mgr.check_transaction(*transaction_id)? {
                    Some(drtioaux::Payload::SubkernelLoadRunReply { succeeded }) => {
                        if let Err(e) = kern_send(&kern::SubkernelLoadRunReply { succeeded: succeeded }) {
                            self.stop(); 
                            self.runtime_exception(e);
                            self.last_finished = Some(SubkernelFinished { 
                                source: self.session.source, id: self.current_id, 
                                with_exception: true, exception_source: aux_mgr.self_destination()
                            });
                        } else {
                            self.session.kernel_state = KernelState::Running;
                        }
                        Ok(())
                    }
                    Some(p) => {
                        error!("subkernel message send received unexpected reply: {:?}", p);
                        Err(Error::DrtioError)
                    }
                    None => Ok(()),
                }
            }
            _ => Ok(())
        }
    }

    pub fn remote_subkernel_finished(&mut self, id: u32, with_exception: bool, exception_source: u8) {
        if with_exception {
            unsafe { kernel_cpu::stop() }
            self.session.kernel_state = KernelState::Absent;
            unsafe { self.cache.unborrow() }
            self.last_finished = Some(SubkernelFinished {
                source: self.session.source, id: self.current_id,
                with_exception: true, exception_source: exception_source
            })
        } else {
            self.session.subkernels_finished.push(id);
        }
    }

    fn process_kern_message(&mut self, aux_mgr: &mut AuxManager, dma_mgr: &mut DmaManager
    ) -> Result<Option<bool>, Error> {
        // returns Ok(with_exception) on finish
        // None if the kernel is still running
        kern_recv(|request| {
            match (request, &self.session.kernel_state) {
                (&kern::LoadReply(_), KernelState::Loaded) |
                    (_, KernelState::DmaUploading { .. }) |
                    (_, KernelState::DmaAwait { .. }) |
                    (_, KernelState::MsgSending { .. }) |
                    (_, KernelState::SubkernelAwaitLoad { .. }) | 
                    (_, KernelState::SubkernelAwaitFinish { .. }) => {
                    // We're standing by; ignore the message.
                    return Ok(None)
                }
                (_, KernelState::Running) => (),
                _ => {
                    unexpected!("unexpected request {:?} from kernel CPU in {:?} state",
                                request, self.session.kernel_state)
                },
            }

            if process_kern_hwreq(request, aux_mgr)? {
                return Ok(None)
            }

            match request {
                &kern::Log(args) => {
                    use core::fmt::Write;
                    self.session.log_buffer
                        .write_fmt(args)
                        .unwrap_or_else(|_| warn!("cannot append to session log buffer"));
                    self.session.flush_log_buffer();
                    kern_acknowledge()
                }

                &kern::LogSlice(arg) => {
                    self.session.log_buffer += arg;
                    self.session.flush_log_buffer();
                    kern_acknowledge()
                }

                &kern::RpcFlush => {
                    // we do not have to do anything about this request,
                    // it is sent by the kernel firmware regardless of RPC being used
                    kern_acknowledge()
                }

                &kern::CacheGetRequest { key } => {
                    let value = self.cache.get(key);
                    kern_send(&kern::CacheGetReply {
                        value: unsafe { mem::transmute(value) }
                    })
                }

                &kern::CachePutRequest { key, value } => {
                    let succeeded = self.cache.put(key, value).is_ok();
                    kern_send(&kern::CachePutReply { succeeded: succeeded })
                }

                &kern::RunFinished => {
                    unsafe { kernel_cpu::stop() }
                    self.session.kernel_state = KernelState::Absent;
                    unsafe { self.cache.unborrow() }

                    return Ok(Some(false))
                }
                &kern::RunException { exceptions, stack_pointers, backtrace } => {
                    unsafe { kernel_cpu::stop() }
                    self.session.kernel_state = KernelState::Absent;
                    unsafe { self.cache.unborrow() }    
                    let exception = slice_kernel_exception(&exceptions, &stack_pointers, &backtrace)?;
                    self.session.last_exception = Some(exception);
                    return Ok(Some(true))
                }

                &kern::DmaRecordStart(name) => {
                    dma_mgr.record_start(name);
                    kern_acknowledge()
                }
                &kern::DmaRecordAppend(data) => {
                    dma_mgr.record_append(data);
                    kern_acknowledge()
                }
                &kern::DmaRecordStop { duration, enable_ddma: _ } => {
                    // ddma is always used on satellites
                    if let Ok(id) = dma_mgr.record_stop(duration, aux_mgr.self_destination()) {
                        let remote_count = dma_mgr.upload_traces(id, aux_mgr)?;
                        if remote_count > 0 {
                            let max_time = clock::get_ms() + 10_000 as u64;
                            self.session.kernel_state = KernelState::DmaUploading { id: id, max_time: max_time };
                            Ok(())
                        } else {
                            kern_acknowledge()
                        }
                    } else {
                        unexpected!("DMAError: found an unsupported call to RTIO devices on master") 
                    }
                }
                &kern::DmaEraseRequest { name } => {
                    dma_mgr.erase_name(name, aux_mgr);
                    kern_acknowledge()
                }
                &kern::DmaRetrieveRequest { name } => {
                    dma_mgr.with_trace(aux_mgr.self_destination(), name, |trace, duration| {
                        kern_send(&kern::DmaRetrieveReply {
                            trace:    trace,
                            duration: duration,
                            uses_ddma: true,
                        })
                    })
                }
                &kern::DmaStartRemoteRequest { id, timestamp } => {
                    let max_time = clock::get_ms() + 10_000 as u64;
                    self.session.kernel_state = KernelState::DmaAwait { id: id as u32, max_time: max_time };
                    dma_mgr.playback_remote(id as u32, timestamp as u64, aux_mgr)?;
                    dma_mgr.playback(aux_mgr.self_destination(), id as u32, timestamp as u64)?;
                    Ok(())
                }

                &kern::SubkernelMsgSend { id, destination: msg_dest, count, tag, data } => {
                    let message_destination;
                    let message_id;
                    if let Some(dest) = msg_dest {
                        message_destination = dest;
                        message_id = id;
                    } else {
                        // return message, return to source
                        message_destination = self.session.source;
                        message_id = self.current_id;
                    }
                    let transaction_id = self.session.messages.accept_outgoing(
                        message_id, message_destination, count, tag, data, aux_mgr)?;
                    // acknowledge after the message is sent
                    self.session.kernel_state = KernelState::MsgSending { transaction_id: transaction_id };
                    Ok(())
                }

                &kern::SubkernelMsgRecvRequest { id, timeout, tags } => {
                    // negative timeout value means no timeout
                    let max_time = if timeout > 0 { clock::get_ms() as i64 + timeout } else { timeout };
                    // ID equal to -1 indicates wildcard for receiving arguments
                    let id = if id == -1 { self.current_id } else { id as u32 };
                    self.session.kernel_state = KernelState::MsgAwait { 
                        id: id, max_time: max_time, tags: tags.to_vec() };
                    Ok(())
                },

                &kern::SubkernelLoadRunRequest { id, destination, run } => {                    
                    let transaction_id = aux_mgr.transact(destination, false, drtioaux::Payload::SubkernelLoadRunRequest { 
                        id: id, run: run
                    })?;
                    self.session.kernel_state = KernelState::SubkernelAwaitLoad { transaction_id: transaction_id };
                    Ok(())
                }

                &kern::SubkernelAwaitFinishRequest{ id, timeout } => {
                    let max_time = if timeout > 0 { clock::get_ms() as i64 + timeout } else { timeout };
                    self.session.kernel_state = KernelState::SubkernelAwaitFinish { max_time: max_time, id: id };
                    Ok(())
                }

                request => unexpected!("unexpected request {:?} from kernel CPU", request)
            }.and(Ok(None))
        })
    }
}

impl Drop for Manager {
    fn drop(&mut self) {
        cricon_select(RtioMaster::Drtio);
        unsafe {
            kernel_cpu::stop() 
        };
    }
}

fn kern_recv<R, F>(f: F) -> Result<R, Error>
        where F: FnOnce(&kern::Message) -> Result<R, Error> {
    if mailbox::receive() == 0 {
        return Err(Error::NoMessage);
    };
    if !kernel_cpu::validate(mailbox::receive()) {
        return Err(Error::InvalidPointer(mailbox::receive()))
    }
    f(unsafe { &*(mailbox::receive() as *const kern::Message) })
}

fn kern_recv_w_timeout<R, F>(timeout: u64, f: F) -> Result<R, Error>
        where F: FnOnce(&kern::Message) -> Result<R, Error> + Copy {
    // sometimes kernel may be too slow to respond immediately
    // (e.g. when receiving external messages)
    // we cannot wait indefinitely to keep the satellite responsive
    // so a timeout is used instead
    let max_time = clock::get_ms() + timeout;
    while clock::get_ms() < max_time {
        match kern_recv(f) {
            Err(Error::NoMessage) => continue,
            anything_else => return anything_else
        }
    }
    Err(Error::NoMessage)
}

fn kern_acknowledge() -> Result<(), Error> {
    mailbox::acknowledge();
    Ok(())
}

fn kern_send(request: &kern::Message) -> Result<(), Error> {
    unsafe { mailbox::send(request as *const _ as usize) }
    while !mailbox::acknowledged() {}
    Ok(())
}

fn slice_kernel_exception(exceptions: &[Option<eh_artiq::Exception>],
    stack_pointers: &[eh_artiq::StackPointerBacktrace],
    backtrace: &[(usize, usize)]
) -> Result<Sliceable, Error> {
    error!("exception in kernel");
    for exception in exceptions {
        error!("{:?}", exception.unwrap());
    }
    error!("stack pointers: {:?}", stack_pointers);
    error!("backtrace: {:?}", backtrace);
    // master will only pass the exception data back to the host:
    let raw_exception: Vec<u8> = Vec::new();
    let mut writer = Cursor::new(raw_exception);
    match (HostKernelException {
        exceptions: exceptions,
        stack_pointers: stack_pointers,
        backtrace: backtrace,
        async_errors: 0
    }).write_to(&mut writer) {
        // save last exception data to be received by master
        Ok(_) => Ok(Sliceable::new(0, writer.into_inner())),
        Err(_) => Err(Error::SubkernelIoError)
    }
}

fn pass_message_to_kernel(message: &Message, tags: &[u8]) -> Result<(), Error> {
    let mut reader = Cursor::new(&message.data);
    let mut current_tags = tags;
    let mut i = 0;
    loop {
        let slot = kern_recv_w_timeout(100, |reply| {
            match reply {
                &kern::RpcRecvRequest(slot) => Ok(slot),
                &kern::RunException { exceptions, stack_pointers, backtrace } => {
                    let exception = slice_kernel_exception(&exceptions, &stack_pointers, &backtrace)?;
                    Err(Error::KernelException(exception))
                },
                other => unexpected!(
                    "expected root value slot from kernel CPU, not {:?}", other)
            }
        })?;
        let res = rpc::recv_return(&mut reader, current_tags, slot, &|size| -> Result<_, Error> {
            if size == 0 {
                return Ok(0 as *mut ())
            }
            kern_send(&kern::RpcRecvReply(Ok(size)))?;
            Ok(kern_recv_w_timeout(100, |reply| {
                match reply {
                    &kern::RpcRecvRequest(slot) => Ok(slot),
                    &kern::RunException { 
                        exceptions,
                        stack_pointers,
                        backtrace 
                    }=> {
                        let exception = slice_kernel_exception(&exceptions, &stack_pointers, &backtrace)?;
                        Err(Error::KernelException(exception))
                    },
                    other => unexpected!(
                        "expected nested value slot from kernel CPU, not {:?}", other)
                }
            })?)
        });
        match res {
            Ok(new_tags) => {
                kern_send(&kern::RpcRecvReply(Ok(0)))?;
                i += 1;
                if i < message.count {
                    // update the tag for next read
                    current_tags = new_tags;
                } else {
                    // should be done by then
                    break;
                }
            },
            Err(_) => unexpected!("expected valid subkernel message data")
        };
    }
    Ok(())
}

fn process_kern_hwreq(request: &kern::Message, aux_mgr: &AuxManager) -> Result<bool, Error> {
    match request {
        &kern::RtioInitRequest => {
            unsafe {
                csr::drtiosat::reset_write(1);
                clock::spin_us(100);
                csr::drtiosat::reset_write(0);
            }
            kern_acknowledge()
        }

        &kern::RtioDestinationStatusRequest { destination } => {
            // only local destination is considered "up"
            // no access to other DRTIO destinations
            kern_send(&kern::RtioDestinationStatusReply { 
                up: destination == aux_mgr.self_destination() })
        }

        &kern::I2cStartRequest { busno } => {
            let succeeded = i2c::start(busno as u8).is_ok();
            kern_send(&kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cRestartRequest { busno } => {
            let succeeded = i2c::restart(busno as u8).is_ok();
            kern_send(&kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cStopRequest { busno } => {
            let succeeded = i2c::stop(busno as u8).is_ok();
            kern_send(&kern::I2cBasicReply { succeeded: succeeded })
        }
        &kern::I2cWriteRequest { busno, data } => {
            match i2c::write(busno as u8, data) {
                Ok(ack) => kern_send(
                    &kern::I2cWriteReply { succeeded: true, ack: ack }),
                Err(_) => kern_send(
                    &kern::I2cWriteReply { succeeded: false, ack: false })
            }
        }
        &kern::I2cReadRequest { busno, ack } => {
            match i2c::read(busno as u8, ack) {
                Ok(data) => kern_send(
                    &kern::I2cReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(
                    &kern::I2cReadReply { succeeded: false, data: 0xff })
            }
        }
        &kern::I2cSwitchSelectRequest { busno, address, mask } => {
            let succeeded = i2c::switch_select(busno as u8, address, mask).is_ok();
            kern_send(&kern::I2cBasicReply { succeeded: succeeded })
        }

        &kern::SpiSetConfigRequest { busno, flags, length, div, cs } => {
            let succeeded = spi::set_config(busno as u8, flags, length, div, cs).is_ok();
            kern_send(&kern::SpiBasicReply { succeeded: succeeded })
        },
        &kern::SpiWriteRequest { busno, data } => {
            let succeeded = spi::write(busno as u8, data).is_ok();
            kern_send(&kern::SpiBasicReply { succeeded: succeeded })
        }
        &kern::SpiReadRequest { busno } => {
            match spi::read(busno as u8) {
                Ok(data) => kern_send(
                    &kern::SpiReadReply { succeeded: true, data: data }),
                Err(_) => kern_send(
                    &kern::SpiReadReply { succeeded: false, data: 0 })
            }
        }

        _ => return Ok(false)
    }.and(Ok(true))
}