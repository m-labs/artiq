use core::{mem, option::NoneError, cmp::min};
use alloc::{string::String, format, vec::Vec, collections::{btree_map::BTreeMap, vec_deque::VecDeque}};
use cslice::AsCSlice;

use board_artiq::{mailbox, spi};
use board_misoc::{csr, clock, i2c};
use proto_artiq::{kernel_proto as kern, session_proto::Reply::KernelException as HostKernelException, rpc_proto as rpc};
use eh::eh_artiq;
use io::{Cursor, ProtoRead};
use kernel::eh_artiq::StackPointerBacktrace;

use cache::Cache;
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

        csr::cri_con::selected_write(2);
        csr::kernel_cpu::reset_write(0);
    }

    pub unsafe fn stop() {
        csr::kernel_cpu::reset_write(1);
        csr::cri_con::selected_write(0);

        mailbox::acknowledge();
    }

    pub fn validate(ptr: usize) -> bool {
        ptr >= KERNELCPU_EXEC_ADDRESS && ptr <= KERNELCPU_LAST_ADDRESS
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum KernelState {
    Absent,
    Loaded,
    Running,
    MsgAwait { max_time: u64 },
    MsgSending,
    ArgAwait
}

#[derive(Debug)]
pub enum Error {
    Load(String),
    KernelNotFound,
    InvalidPointer(usize),
    Unexpected(String),
    NoMessage,
    AwaitingMessage,
    SubkernelIoError
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

macro_rules! unexpected {
    ($($arg:tt)*) => (return Err(Error::Unexpected(format!($($arg)*))));
}

/* represents data that has to be sent to Master */
struct Sliceable {
    it: usize,
    data: Vec<u8>
}

/* represents interkernel messages */
struct Message {
    tag: u8,
    data: Vec<u8>
}

#[derive(PartialEq)]
enum OutMessageState {
    NoMessage,
    MessageReady,
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
    cache: Cache,
    kernel_state: KernelState,
    log_buffer: String,
    last_exception: Option<Sliceable>,
    messages: MessageManager
}

#[derive(Debug)]
struct KernelData {
    data: Vec<u8>,
    complete: bool
}

pub struct Manager {
    kernels: BTreeMap<u32, KernelData>,
    current_id: u32,
    session: Session,
}

pub struct SubkernelFinished {
    pub id: u32,
    pub with_exception: bool
}

pub struct SliceMeta {
    pub len: u16,
    pub last: bool
}

macro_rules! get_slice_fn {
    ( $name:tt, $size:expr ) => {
        pub fn $name(&mut self, data_slice: &mut [u8; $size]) -> SliceMeta {
            if self.data.len() == 0 {
                return SliceMeta { len: 0, last: true };
            }
            let len = min($size, self.data.len() - self.it);
            let last = self.it + len == self.data.len();
    
            data_slice[..len].clone_from_slice(&self.data[self.it..self.it+len]);
            self.it += len;
    
            SliceMeta {
                len: len as u16,
                last: last
            }
        }
    };
}

impl Sliceable {
    pub fn new(data: Vec<u8>) -> Sliceable {
        Sliceable {
            it: 0,
            data: data
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

    pub fn handle_incoming(&mut self, last: bool, length: usize, data: &[u8; MASTER_PAYLOAD_MAX_SIZE]) {
        // called when receiving a message from master
        match self.in_buffer.as_mut() {
            Some(message) => message.data.extend(&data[..length]),
            None => {
                self.in_buffer = Some(Message {
                    tag: data[0],
                    data: data[1..length].to_vec()
                });
            }
        };
        if last {
            // when done, remove from working queue
            self.in_queue.push_back(self.in_buffer.take().unwrap());
        }
    }

    pub fn is_outgoing_ready(&mut self) -> bool {
        // called by main loop, to see if there's anything to send, will send it afterwards
        match self.out_state {
            OutMessageState::MessageReady => {
                self.out_state = OutMessageState::MessageBeingSent;
                true
            },
            _ => false
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
        if meta.last {
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

    pub fn accept_outgoing(&mut self, tag: &[u8], data: *const *const ()) -> Result<(), Error>  {
        let mut writer = Cursor::new(Vec::new());
        rpc::send_args(&mut writer, 0, tag, data)?;
        // skip service tag
        self.out_message = Some(Sliceable::new(writer.into_inner().split_off(4)));
        self.out_state = OutMessageState::MessageReady;
        Ok(())
    }

    pub fn get_incoming(&mut self) -> Option<Message> {
        self.in_queue.pop_front()
    }
}

impl Session {
    pub fn new() -> Session {
        Session {
            cache: Cache::new(),
            kernel_state: KernelState::Absent,
            log_buffer: String::new(),
            last_exception: None,
            messages: MessageManager::new()
        }
    }

    fn running(&self) -> bool {
        match self.kernel_state {
            KernelState::Absent  | KernelState::Loaded  => false,
            KernelState::Running | KernelState::ArgAwait |
            KernelState::MsgAwait { .. } | KernelState::MsgSending => true
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
        }
    }

    pub fn add(&mut self, id: u32, last: bool, data: &[u8], data_len: usize) -> Result<(), Error> {
        let kernel = match self.kernels.get_mut(&id) {
            Some(kernel) => {
                if kernel.complete {
                    // replace entry
                    self.kernels.remove(&id);
                    self.kernels.insert(id, KernelData {
                        data: Vec::new(),
                        complete: false });
                    self.kernels.get_mut(&id)?
                } else {
                    kernel
                }
            },
            None => {
                self.kernels.insert(id, KernelData {
                    data: Vec::new(),
                    complete: false });
                self.kernels.get_mut(&id)?
            },
        };
        kernel.data.extend(&data[0..data_len]);

        kernel.complete = last;
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
        unsafe { self.session.cache.unborrow() }
    }

    pub fn run(&mut self, id: u32) -> Result<(), Error> {
        info!("starting subkernel #{}", id);
        if self.session.kernel_state != KernelState::Loaded
            || self.current_id != id {
            self.load(id)?;
        }
        self.session.kernel_state = KernelState::Running;
    
        kern_acknowledge()
    }

    pub fn message_handle_incoming(&mut self, last: bool, length: usize, slice: &[u8; MASTER_PAYLOAD_MAX_SIZE]) {
        if !self.is_running() {
            return;
        }
        self.session.messages.handle_incoming(last, length, slice);
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

    pub fn message_is_ready(&mut self) -> bool {
        self.session.messages.is_outgoing_ready()
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

            kern_send(&kern::LoadRequest(&self.kernels.get(&id)?.data)).unwrap();
            kern_recv(|reply| {
                match reply {
                    kern::LoadReply(Ok(())) => {
                        self.session.kernel_state = KernelState::Loaded;
                        Ok(())
                    }
                    kern::LoadReply(Err(error)) => {
                        kernel_cpu::stop();
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
            None => SliceMeta { len: 0, last: true }
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
            Ok(_) => self.session.last_exception = Some(Sliceable::new(writer.into_inner())),
            Err(_) => error!("Error writing exception data")
        }
    }
    

    pub fn process_kern_requests(&mut self, rank: u8) -> Option<SubkernelFinished> {
        if !self.is_running() {
            return None;
        }

        match process_external_messages(&mut self.session) {
            Ok(()) => (),
            Err(Error::AwaitingMessage) => return None, // kernel still waiting, do not process kernel messages
            Err(e) => { 
                error!("Error while running processing external messages: {:?}", e);
                self.stop();
                self.runtime_exception(e);
                return Some(SubkernelFinished { id: self.current_id, with_exception: true })
             }
        }

        match process_kern_message(&mut self.session, rank) {
            Ok(Some(with_exception)) => Some(SubkernelFinished { id: self.current_id, with_exception: with_exception }),
            Ok(None) | Err(Error::NoMessage) => None,
            Err(e) => { 
                error!("Error while running kernel: {:?}", e); 
                self.stop(); 
                self.runtime_exception(e);
                Some(SubkernelFinished { id: self.current_id, with_exception: true })
            }
        }
    }
}

impl Drop for Manager {
    fn drop(&mut self) {
        unsafe { kernel_cpu::stop() };
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

fn pass_message_to_kernel(message: &Message) -> Result<(), Error> {
    let mut reader = Cursor::new(&message.data);
    let mut tag: [u8; 1] = [message.tag];
    loop {
        let slot = kern_recv_w_timeout(100, |reply| {
            match reply {
                &kern::RpcRecvRequest(slot) => Ok(slot),
                other => unexpected!(
                    "expected root value slot from kernel CPU, not {:?}", other)
            }
        })?;

        let res = rpc::recv_return(&mut reader, &tag, slot, &|size| -> Result<_, Error> {
            if size == 0 {
                return Ok(0 as *mut ())
            }
            kern_send(&kern::RpcRecvReply(Ok(size)))?;
            Ok(kern_recv_w_timeout(100, |reply| {
                match reply {
                    &kern::RpcRecvRequest(slot) => Ok(slot),
                    other => unexpected!(
                        "expected nested value slot from kernel CPU, not {:?}", other)
                }
            })?)
        });
        match res {
            Ok(_) => kern_send(&kern::RpcRecvReply(Ok(0)))?,
            Err(_) => unexpected!("expected valid subkernel message data")
        };
        match reader.read_u8() {
            Ok(0) | Err(_) => break, // reached the end of data, we're done
            Ok(t) => { tag[0] = t; } // update the tag for next read
        }
    }
    Ok(())
}

fn process_external_messages(session: &mut Session) -> Result<(), Error> {
    match session.kernel_state {
        KernelState::MsgAwait { max_time } => {
            if max_time > clock::get_ms() {
                kern_send(&kern::SubkernelMsgRecvReply { timeout: true })?;
                session.kernel_state = KernelState::Running;
                return Ok(())
            }
            if let Some(message) = session.messages.get_incoming() {
                kern_send(&kern::SubkernelMsgRecvReply { timeout: false })?;
                session.kernel_state = KernelState::Running;
                pass_message_to_kernel(&message)
            } else {
                Err(Error::AwaitingMessage)
            }
        },
        KernelState::ArgAwait => {
            if let Some(message) = session.messages.get_incoming() {
                kern_acknowledge()?;
                session.kernel_state = KernelState::Running;
                pass_message_to_kernel(&message)
            } else {
                Err(Error::AwaitingMessage)
            }
        }
        KernelState::MsgSending => {
            if session.messages.was_message_acknowledged() {
                session.kernel_state = KernelState::Running;
                kern_acknowledge()
            } else {
                Err(Error::AwaitingMessage)
            }
        },
        _ => Ok(())
    }
}

fn process_kern_message(session: &mut Session, rank: u8) -> Result<Option<bool>, Error> {
    // returns Ok(with_exception) on finish
    // None if the kernel is still running
    kern_recv(|request| {
        match (request, session.kernel_state) {
            (&kern::LoadReply(_), KernelState::Loaded) => {
                // We're standing by; ignore the message.
                return Ok(None)
            }
            (_, KernelState::Running) => (),
            _ => {
                unexpected!("unexpected request {:?} from kernel CPU in {:?} state",
                            request, session.kernel_state)
            },
        }

        if process_kern_hwreq(request, rank)? {
            return Ok(None)
        }

        match request {
            &kern::Log(args) => {
                use core::fmt::Write;
                session.log_buffer
                       .write_fmt(args)
                       .unwrap_or_else(|_| warn!("cannot append to session log buffer"));
                session.flush_log_buffer();
                kern_acknowledge()
            }

            &kern::LogSlice(arg) => {
                session.log_buffer += arg;
                session.flush_log_buffer();
                kern_acknowledge()
            }

            &kern::RpcFlush => {
                // we do not have to do anything about this request,
                // it is sent by the kernel firmware regardless of RPC being used
                kern_acknowledge()
            }

            &kern::CacheGetRequest { key } => {
                let value = session.cache.get(key);
                kern_send(&kern::CacheGetReply {
                    value: unsafe { mem::transmute(value) }
                })
            }

            &kern::CachePutRequest { key, value } => {
                let succeeded = session.cache.put(key, value).is_ok();
                kern_send(&kern::CachePutReply { succeeded: succeeded })
            }

            &kern::RunFinished => {
                unsafe { kernel_cpu::stop() }
                session.kernel_state = KernelState::Absent;
                unsafe { session.cache.unborrow() }

                return Ok(Some(false))
            }
            &kern::RunException {
                exceptions,
                stack_pointers,
                backtrace
            } => {
                unsafe { kernel_cpu::stop() }
                session.kernel_state = KernelState::Absent;

                error!("exception in flash kernel");
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
                    Ok(_) => session.last_exception = Some(Sliceable::new(writer.into_inner())),
                    Err(_) => error!("Error writing exception data")
                }
                return Ok(Some(true))
            }

            &kern::SubkernelMsgSend { id: _, tag, data } => {
                session.messages.accept_outgoing(tag, data)?;
                // acknowledge after the message is sent
                session.kernel_state = KernelState::MsgSending;
                Ok(())
            }

            &kern::SubkernelMsgRecvRequest { id: _, timeout } => {
                let max_time = clock::get_ms() + timeout as u64;
                session.kernel_state = KernelState::MsgAwait { max_time: max_time };
                Ok(())
            },

            &kern::SubkernelArgRecvRequest => {
                session.kernel_state = KernelState::ArgAwait;
                Ok(())
            }

            request => unexpected!("unexpected request {:?} from kernel CPU", request)
        }.and(Ok(None))
    })
}

pub fn process_kern_hwreq(request: &kern::Message, rank: u8) -> Result<bool, Error> {
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
                up: destination == rank })
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