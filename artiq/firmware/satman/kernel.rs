use core::{mem, option::NoneError, cmp::min};
use alloc::{string::String, format, vec::Vec, collections::{btree_map::BTreeMap, vec_deque::VecDeque}};
use cslice::AsCSlice;

use board_artiq::{drtioaux, drtio_routing::RoutingTable, mailbox, spi};
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
use routing::Router;
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
    MsgAwait { max_time: u64, tags: Vec<u8> },
    MsgSending,
    SubkernelAwaitLoad,
    SubkernelAwaitFinish { max_time: u64, id: u32 }
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
    KernelException(Sliceable)
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

macro_rules! unexpected {
    ($($arg:tt)*) => (return Err(Error::Unexpected(format!($($arg)*))));
}

/* represents data that has to be sent to Master */
#[derive(Debug)]
pub struct Sliceable {
    it: usize,
    data: Vec<u8>,
    destination: u8
}

/* represents interkernel messages */
struct Message {
    count: u8,
    data: Vec<u8>
}

#[derive(PartialEq)]
enum OutMessageState {
    NoMessage,
    MessageBeingSent,
    MessageSent,
    MessageAcknowledged
}

/* for dealing with incoming and outgoing interkernel messages */
struct MessageManager {
    out_message: Option<Sliceable>,
    out_state: OutMessageState,
    in_queue: VecDeque<Message>,
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

pub struct SliceMeta {
    pub destination: u8,
    pub len: u16,
    pub status: PayloadStatus
}

macro_rules! get_slice_fn {
    ( $name:tt, $size:expr ) => {
        pub fn $name(&mut self, data_slice: &mut [u8; $size]) -> SliceMeta {
            let first = self.it == 0;
            let len = min($size, self.data.len() - self.it);
            let last = self.it + len == self.data.len();
            let status = PayloadStatus::from_status(first, last);
            data_slice[..len].clone_from_slice(&self.data[self.it..self.it+len]);
            self.it += len;
    
            SliceMeta {
                destination: self.destination,
                len: len as u16,
                status: status
            }
        }
    };
}

impl Sliceable {
    pub fn new(destination: u8, data: Vec<u8>) -> Sliceable {
        Sliceable {
            it: 0,
            data: data,
            destination: destination
        }
    }

    get_slice_fn!(get_slice_sat, SAT_PAYLOAD_MAX_SIZE);
    get_slice_fn!(get_slice_master, MASTER_PAYLOAD_MAX_SIZE);
}

impl MessageManager {
    pub fn new() -> MessageManager {
        MessageManager {
            out_message: None,
            out_state: OutMessageState::NoMessage,
            in_queue: VecDeque::new(),
            in_buffer: None
        }
    }

    pub fn handle_incoming(&mut self, status: PayloadStatus, length: usize, data: &[u8; MASTER_PAYLOAD_MAX_SIZE]) {
        // called when receiving a message from master
        if status.is_first() {
            // clear the buffer for first message
            self.in_buffer = None;
        }
        match self.in_buffer.as_mut() {
            Some(message) => message.data.extend(&data[..length]),
            None => {
                self.in_buffer = Some(Message {
                    count: data[0],
                    data: data[1..length].to_vec()
                });
            }
        };
        if status.is_last() {
            // when done, remove from working queue
            self.in_queue.push_back(self.in_buffer.take().unwrap());
        }
    }

    pub fn was_message_acknowledged(&mut self) -> bool {
        match self.out_state {
            OutMessageState::MessageAcknowledged => {
                self.out_state = OutMessageState::NoMessage;
                true
            },
            _ => false
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
                self.out_state = OutMessageState::MessageAcknowledged;
                false
            },
            _ => { 
                warn!("received unsolicited SubkernelMessageAck"); 
                false 
            }
        }
    }

    pub fn accept_outgoing(&mut self, id: u32, self_destination: u8, destination: u8, 
        count: u8, tag: &[u8], data: *const *const (), 
        routing_table: &RoutingTable, rank: u8, router: &mut Router
    ) -> Result<(), Error>  {
        let mut writer = Cursor::new(Vec::new());
        rpc::send_args(&mut writer, 0, tag, data, false)?;
        // skip service tag, but write the count
        let mut data = writer.into_inner().split_off(3);
        data[0] = count;
        self.out_message = Some(Sliceable::new(destination, data));

        let mut data_slice: [u8; MASTER_PAYLOAD_MAX_SIZE] = [0; MASTER_PAYLOAD_MAX_SIZE];
        self.out_state = OutMessageState::MessageBeingSent;
        let meta = self.get_outgoing_slice(&mut data_slice).unwrap();
        router.route(drtioaux::Packet::SubkernelMessage {
                source: self_destination, destination: destination, id: id,
                status: meta.status, length: meta.len as u16, data: data_slice
        }, routing_table, rank, self_destination);
        Ok(())
    }

    pub fn get_incoming(&mut self) -> Option<Message> {
        self.in_queue.pop_front()
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
            KernelState::Absent  | KernelState::Loaded  => false,
            KernelState::Running | KernelState::MsgAwait { .. } |
                KernelState::MsgSending | KernelState::SubkernelAwaitLoad |
                KernelState::SubkernelAwaitFinish { .. } => true
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

    pub fn get_current_id(&self) -> Option<u32> {
        match self.is_running() {
            true => Some(self.current_id),
            false => None
        }
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

    pub fn message_handle_incoming(&mut self, status: PayloadStatus, length: usize, slice: &[u8; MASTER_PAYLOAD_MAX_SIZE]) {
        if !self.is_running() {
            return;
        }
        self.session.messages.handle_incoming(status, length, slice);
    }
    
    pub fn message_get_slice(&mut self, slice: &mut [u8; MASTER_PAYLOAD_MAX_SIZE]) -> Option<SliceMeta> {
        if !self.is_running() {
            return None;
        }
        self.session.messages.get_outgoing_slice(slice)
    }

    pub fn message_ack_slice(&mut self) -> bool {
        if !self.is_running() {
            warn!("received unsolicited SubkernelMessageAck");
            return false;
        }
        self.session.messages.ack_slice()
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

    pub fn process_kern_requests(&mut self, router: &mut Router, routing_table: &RoutingTable, rank: u8, destination: u8) {
        macro_rules! finished {
            ($with_exception:expr) => {{ Some(SubkernelFinished { 
                source: self.session.source, id: self.current_id, 
                with_exception: $with_exception, exception_source: destination 
            }) }}
        }

        if let Some(subkernel_finished) = self.last_finished.take() {
            info!("subkernel {} finished, with exception: {}", subkernel_finished.id, subkernel_finished.with_exception);
            router.route(drtioaux::Packet::SubkernelFinished {
                destination: subkernel_finished.source, id: subkernel_finished.id, 
                with_exception: subkernel_finished.with_exception, exception_src: subkernel_finished.exception_source
            }, &routing_table, rank, destination);
        }

        if !self.is_running() {
            return;
        }

        match self.process_external_messages() {
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

        match self.process_kern_message(router, routing_table, rank, destination) {
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

    fn process_external_messages(&mut self) -> Result<(), Error> {
        match &self.session.kernel_state {
            KernelState::MsgAwait { max_time, tags } => {
                if clock::get_ms() > *max_time {
                    kern_send(&kern::SubkernelMsgRecvReply { status: kern::SubkernelStatus::Timeout, count: 0 })?;
                    self.session.kernel_state = KernelState::Running;
                    return Ok(())
                }
                if let Some(message) = self.session.messages.get_incoming() {
                    kern_send(&kern::SubkernelMsgRecvReply { status: kern::SubkernelStatus::NoError, count: message.count })?;
                    let tags = tags.clone();
                    self.session.kernel_state = KernelState::Running;
                    pass_message_to_kernel(&message, &tags)
                } else {
                    Err(Error::AwaitingMessage)
                }
            },
            KernelState::MsgSending => {
                if self.session.messages.was_message_acknowledged() {
                    self.session.kernel_state = KernelState::Running;
                    kern_acknowledge()
                } else {
                    Err(Error::AwaitingMessage)
                }
            },
            KernelState::SubkernelAwaitFinish { max_time, id } => {
                if clock::get_ms() > *max_time {
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
            _ => Ok(())
        }
    }

    pub fn subkernel_load_run_reply(&mut self, succeeded: bool, self_destination: u8) {
        if self.session.kernel_state == KernelState::SubkernelAwaitLoad {
            if let Err(e) = kern_send(&kern::SubkernelLoadRunReply { succeeded: succeeded }) {
                self.stop(); 
                self.runtime_exception(e);
                self.last_finished = Some(SubkernelFinished { 
                    source: self.session.source, id: self.current_id, 
                    with_exception: true, exception_source: self_destination 
                })
            } else {
                self.session.kernel_state = KernelState::Running;
            }
        } else {
            warn!("received unsolicited SubkernelLoadRunReply");
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

    fn process_kern_message(&mut self, router: &mut Router, 
        routing_table: &RoutingTable,
        rank: u8, destination: u8
    ) -> Result<Option<bool>, Error> {
        // returns Ok(with_exception) on finish
        // None if the kernel is still running
        kern_recv(|request| {
            match (request, &self.session.kernel_state) {
                (&kern::LoadReply(_), KernelState::Loaded) => {
                    // We're standing by; ignore the message.
                    return Ok(None)
                }
                (_, KernelState::Running) => (),
                _ => {
                    unexpected!("unexpected request {:?} from kernel CPU in {:?} state",
                                request, self.session.kernel_state)
                },
            }

            if process_kern_hwreq(request, destination)? {
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

                &kern::SubkernelMsgSend { id: _, destination: msg_dest, count, tag, data } => {
                    let dest = match msg_dest {
                        Some(dest) => dest,
                        None => self.session.source
                    };
                    self.session.messages.accept_outgoing(self.current_id, destination,
                        dest, count, tag, data, 
                        routing_table, rank, router)?;
                    // acknowledge after the message is sent
                    self.session.kernel_state = KernelState::MsgSending;
                    Ok(())
                }

                &kern::SubkernelMsgRecvRequest { id: _, timeout, tags } => {
                    let max_time = clock::get_ms() + timeout as u64;
                    self.session.kernel_state = KernelState::MsgAwait { max_time: max_time, tags: tags.to_vec() };
                    Ok(())
                },

                &kern::SubkernelLoadRunRequest { id, destination: sk_destination, run } => {
                    self.session.kernel_state = KernelState::SubkernelAwaitLoad;
                    router.route(drtioaux::Packet::SubkernelLoadRunRequest { 
                        source: destination, destination: sk_destination, id: id, run: run 
                    }, routing_table, rank, destination);
                    kern_acknowledge()
                }

                &kern::SubkernelAwaitFinishRequest{ id, timeout } => {
                    let max_time = clock::get_ms() + timeout as u64;
                    self.session.kernel_state = KernelState::SubkernelAwaitFinish { max_time: max_time, id: id };
                    kern_acknowledge()
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

fn process_kern_hwreq(request: &kern::Message, self_destination: u8) -> Result<bool, Error> {
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
                up: destination == self_destination })
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