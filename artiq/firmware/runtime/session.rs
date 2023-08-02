use core::{mem, str, cell::{Cell, RefCell}, fmt::Write as FmtWrite};
use alloc::{vec::Vec, string::{String, ToString}};
use byteorder::{ByteOrder, NativeEndian};
use cslice::CSlice;

use io::{Read, Write, Error as IoError};
#[cfg(has_drtio)]
use io::{Cursor, ProtoRead};
use board_misoc::{ident, cache, config};
use {mailbox, rpc_queue, kernel};
use urc::Urc;
use sched::{ThreadHandle, Io, Mutex, TcpListener, TcpStream, Error as SchedError};
use rtio_clocking;
use rtio_dma::Manager as DmaManager;
#[cfg(has_drtio)]
use rtio_dma::remote_dma;
#[cfg(has_drtio)]
use kernel::subkernel;
use rtio_mgt::get_async_errors;
use cache::Cache;
use kern_hwreq;
use board_artiq::drtio_routing;

use rpc_proto as rpc;
use session_proto as host;
use kernel_proto as kern;

#[derive(Fail, Debug)]
pub enum Error<T> {
    #[fail(display = "cannot load kernel: {}", _0)]
    Load(String),
    #[fail(display = "kernel not found")]
    KernelNotFound,
    #[fail(display = "invalid kernel CPU pointer: {:#08x}", _0)]
    InvalidPointer(usize),
    #[fail(display = "RTIO clock failure")]
    ClockFailure,
    #[fail(display = "protocol error: {}", _0)]
    Protocol(#[cause] host::Error<T>),
    #[fail(display = "subkernel io error")]
    SubkernelIoError,
    #[fail(display = "{}", _0)]
    Unexpected(String),
}

impl<T> From<host::Error<T>> for Error<T> {
    fn from(value: host::Error<T>) -> Error<T> {
        Error::Protocol(value)
    }
}

impl From<SchedError> for Error<SchedError> {
    fn from(value: SchedError) -> Error<SchedError> {
        Error::Protocol(host::Error::Io(IoError::Other(value)))
    }
}

impl From<IoError<SchedError>> for Error<SchedError> {
    fn from(value: IoError<SchedError>) -> Error<SchedError> {
        Error::Protocol(host::Error::Io(value))
    }
}

impl From<&str> for Error<SchedError> {
    fn from(value: &str) -> Error<SchedError> {
        Error::Unexpected(value.to_string())
    }
}

impl From<io::Error<!>> for Error<SchedError> {
    fn from(_value: io::Error<!>) -> Error<SchedError> {
        Error::SubkernelIoError
    }
}

macro_rules! unexpected {
     ($($arg:tt)*) => (return Err(Error::Unexpected(format!($($arg)*))));
}

// Persistent state
#[derive(Debug)]
struct Congress {
    cache: Cache,
    dma_manager: DmaManager,
    finished_cleanly: Cell<bool>
}

impl Congress {
    fn new() -> Congress {
        Congress {
            cache: Cache::new(),
            dma_manager: DmaManager::new(),
            finished_cleanly: Cell::new(true)
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum KernelState {
    Absent,
    Loaded,
    Running,
    RpcWait
}

// Per-connection state
#[derive(Debug)]
struct Session<'a> {
    congress: &'a mut Congress,
    kernel_state: KernelState,
    log_buffer: String
}

impl<'a> Session<'a> {
    fn new(congress: &mut Congress) -> Session {
        Session {
            congress: congress,
            kernel_state: KernelState::Absent,
            log_buffer: String::new()
        }
    }

    fn running(&self) -> bool {
        match self.kernel_state {
            KernelState::Absent  | KernelState::Loaded  => false,
            KernelState::Running | KernelState::RpcWait => true
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

impl<'a> Drop for Session<'a> {
    fn drop(&mut self) {
        unsafe { kernel::stop() }
    }
}

fn host_read<R>(reader: &mut R) -> Result<host::Request, Error<R::ReadError>>
    where R: Read + ?Sized
{
    let request = host::Request::read_from(reader)?;
    match &request {
        &host::Request::LoadKernel(_) => debug!("comm<-host LoadLibrary(...)"),
        &host::Request::UploadSubkernel { id, destination, kernel: _} => debug!(
            "comm<-host UploadSubkernel(id: {}, destination: {}, ...)", id, destination),
        _ => debug!("comm<-host {:?}", request)
    }
    Ok(request)
}

fn host_write<W>(writer: &mut W, reply: host::Reply) -> Result<(), IoError<W::WriteError>>
    where W: Write + ?Sized
{
    debug!("comm->host {:?}", reply);
    reply.write_to(writer)
}

pub fn kern_send(io: &Io, request: &kern::Message) -> Result<(), Error<SchedError>> {
    match request {
        &kern::LoadRequest(_) => debug!("comm->kern LoadRequest(...)"),
        &kern::DmaRetrieveReply { trace, duration, uses_ddma } => {
            if trace.map(|data| data.len() > 100).unwrap_or(false) {
                debug!("comm->kern DmaRetrieveReply {{ trace: ..., duration: {:?}, uses_ddma: {} }}", duration, uses_ddma)
            } else {
                debug!("comm->kern {:?}", request)
            }
        }
        _ => debug!("comm->kern {:?}", request)
    }
    unsafe { mailbox::send(request as *const _ as usize) }
    Ok(io.until(mailbox::acknowledged)?)
}

fn kern_recv_notrace<R, F>(io: &Io, f: F) -> Result<R, Error<SchedError>>
        where F: FnOnce(&kern::Message) -> Result<R, Error<SchedError>> {
    io.until(|| mailbox::receive() != 0)?;
    if !kernel::validate(mailbox::receive()) {
        return Err(Error::InvalidPointer(mailbox::receive()))
    }

    f(unsafe { &*(mailbox::receive() as *const kern::Message) })
}

fn kern_recv_dotrace(reply: &kern::Message) {
    match reply {
        &kern::Log(_) => debug!("comm<-kern Log(...)"),
        &kern::LogSlice(_) => debug!("comm<-kern LogSlice(...)"),
        &kern::DmaRecordAppend(data) => {
            if data.len() > 100 {
                debug!("comm<-kern DmaRecordAppend([_; {:#x}])", data.len())
            } else {
                debug!("comm<-kern {:?}", reply)
            }
        }
        _ => debug!("comm<-kern {:?}", reply)
    }
}

#[inline(always)]
fn kern_recv<R, F>(io: &Io, f: F) -> Result<R, Error<SchedError>>
        where F: FnOnce(&kern::Message) -> Result<R, Error<SchedError>> {
    kern_recv_notrace(io, |reply| {
        kern_recv_dotrace(reply);
        f(reply)
    })
}

pub fn kern_acknowledge() -> Result<(), Error<SchedError>> {
    mailbox::acknowledge();
    Ok(())
}

unsafe fn kern_load(io: &Io, session: &mut Session, library: &[u8])
                   -> Result<(), Error<SchedError>> {
    if session.running() {
        unexpected!("attempted to load a new kernel while a kernel was running")
    }

    kernel::start();

    kern_send(io, &kern::LoadRequest(&library))?;
    kern_recv(io, |reply| {
        match reply {
            kern::LoadReply(Ok(())) => {
                session.kernel_state = KernelState::Loaded;
                Ok(())
            }
            kern::LoadReply(Err(error)) => {
                kernel::stop();
                Err(Error::Load(format!("{}", error)))
            }
            other =>
                unexpected!("unexpected kernel CPU reply to load request: {:?}", other)
        }
    })
}

fn kern_run(session: &mut Session) -> Result<(), Error<SchedError>> {
    if session.kernel_state != KernelState::Loaded {
        unexpected!("attempted to run a kernel while not in Loaded state")
    }

    session.kernel_state = KernelState::Running;
    // TODO: make this a separate request
    kern_acknowledge()
}

fn process_host_message(io: &Io, _aux_mutex: &Mutex, _ddma_mutex: &Mutex, _subkernel_mutex: &Mutex,
                        _routing_table: &drtio_routing::RoutingTable, stream: &mut TcpStream,
                        session: &mut Session) -> Result<(), Error<SchedError>> {
    match host_read(stream)? {
        host::Request::SystemInfo => {
            host_write(stream, host::Reply::SystemInfo {
                ident: ident::read(&mut [0; 64]),
                finished_cleanly: session.congress.finished_cleanly.get()
            })?;
            session.congress.finished_cleanly.set(true)
        }

        host::Request::LoadKernel(kernel) => {
            #[cfg(has_drtio)]
            subkernel::message_clear_queue(io, _subkernel_mutex);

            match unsafe { kern_load(io, session, &kernel) } {
                Ok(()) => host_write(stream, host::Reply::LoadCompleted)?,
                Err(error) => {
                    let mut description = String::new();
                    write!(&mut description, "{}", error).unwrap();
                    host_write(stream, host::Reply::LoadFailed(&description))?;
                    kern_acknowledge()?;
                }
            }
        },
        host::Request::RunKernel =>
            match kern_run(session) {
                Ok(()) => (),
                Err(_) => host_write(stream, host::Reply::KernelStartupFailed)?
            },

        host::Request::RpcReply { tag } => {
            if session.kernel_state != KernelState::RpcWait {
                unexpected!("unsolicited RPC reply")
            }

            let slot = kern_recv(io, |reply| {
                match reply {
                    &kern::RpcRecvRequest(slot) => Ok(slot),
                    other => unexpected!(
                        "expected root value slot from kernel CPU, not {:?}", other)
                }
            })?;
            rpc::recv_return(stream, &tag, slot, &|size| -> Result<_, Error<SchedError>> {
                if size == 0 {
                    // Don't try to allocate zero-length values, as RpcRecvReply(0) is
                    // used to terminate the kernel-side receive loop.
                    return Ok(0 as *mut ())
                }
                kern_send(io, &kern::RpcRecvReply(Ok(size)))?;
                Ok(kern_recv(io, |reply| {
                    match reply {
                        &kern::RpcRecvRequest(slot) => Ok(slot),
                        other => unexpected!(
                            "expected nested value slot from kernel CPU, not {:?}", other)
                    }
                })?)
            })?;
            kern_send(io, &kern::RpcRecvReply(Ok(0)))?;

            session.kernel_state = KernelState::Running
        }

        host::Request::RpcException {
            id, message, param, file, line, column, function
        } => {
            if session.kernel_state != KernelState::RpcWait {
                unexpected!("unsolicited RPC reply")
            }

            kern_recv(io, |reply| {
                match reply {
                    &kern::RpcRecvRequest(_) => Ok(()),
                    other => unexpected!(
                        "expected (ignored) root value slot from kernel CPU, not {:?}", other)
                }
            })?;

            unsafe {
                let exn = eh::eh_artiq::Exception {
                    id:       id,
                    message:  CSlice::new(message as *const u8, usize::MAX),
                    param:    param,
                    file:     CSlice::new(file as *const u8, usize::MAX),
                    line:     line,
                    column:   column,
                    function: CSlice::new(function as *const u8, usize::MAX),
                };
                kern_send(io, &kern::RpcRecvReply(Err(exn)))?;
            }

            session.kernel_state = KernelState::Running
        }

        host::Request::UploadSubkernel { id: _id, destination: _dest, kernel: _kernel } => {
            #[cfg(has_drtio)]
            {
                subkernel::add_subkernel(io, _subkernel_mutex, _id, _dest, _kernel);
                match subkernel::upload(io, _aux_mutex, _ddma_mutex, _subkernel_mutex, _routing_table, _id) {
                    Ok(_) => host_write(stream, host::Reply::LoadCompleted)?,
                    Err(error) => {
                        let mut description = String::new();
                        write!(&mut description, "{}", error).unwrap();
                        host_write(stream, host::Reply::LoadFailed(&description))?
                    }
                }
            }
            #[cfg(not(has_drtio))]
            host_write(stream, host::Reply::LoadFailed("No DRTIO on this system, subkernels are not supported"))?
        }
    }

    Ok(())
}

fn process_kern_message(io: &Io, aux_mutex: &Mutex,
                        routing_table: &drtio_routing::RoutingTable,
                        up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
                        ddma_mutex: &Mutex, subkernel_mutex: &Mutex, mut stream: Option<&mut TcpStream>,
                        session: &mut Session) -> Result<bool, Error<SchedError>> {
    kern_recv_notrace(io, |request| {
        match (request, session.kernel_state) {
            (&kern::LoadReply(_), KernelState::Loaded) |
            (&kern::RpcRecvRequest(_), KernelState::RpcWait) => {
                // We're standing by; ignore the message.
                return Ok(false)
            }
            (_, KernelState::Running) => (),
            _ => {
                unexpected!("unexpected request {:?} from kernel CPU in {:?} state",
                            request, session.kernel_state)
            }
        }

        kern_recv_dotrace(request);

        if kern_hwreq::process_kern_hwreq(io, aux_mutex, routing_table, up_destinations, request)? {
            return Ok(false)
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

            &kern::DmaRecordStart(name) => {
                if let Some(_id) = session.congress.dma_manager.record_start(name) {
                    // replace the record
                    #[cfg(has_drtio)]
                    remote_dma::erase(io, aux_mutex, ddma_mutex, routing_table, _id);
                }
                kern_acknowledge()
            }
            &kern::DmaRecordAppend(data) => {
                session.congress.dma_manager.record_append(data);
                kern_acknowledge()
            }
            &kern::DmaRecordStop { duration, enable_ddma } => {
                let _id = session.congress.dma_manager.record_stop(duration, enable_ddma, io, ddma_mutex);
                #[cfg(has_drtio)]
                if enable_ddma {
                    remote_dma::upload_traces(io, aux_mutex, ddma_mutex, routing_table, _id);
                }
                cache::flush_l2_cache();
                kern_acknowledge()
            }
            &kern::DmaEraseRequest { name } => {
                #[cfg(has_drtio)]
                if let Some(id) = session.congress.dma_manager.get_id(name) {
                    remote_dma::erase(io, aux_mutex, ddma_mutex, routing_table, *id);
                }
                session.congress.dma_manager.erase(name);
                kern_acknowledge()
            }
            &kern::DmaRetrieveRequest { name } => {
                session.congress.dma_manager.with_trace(name, |trace, duration| {
                    #[cfg(has_drtio)]
                    let uses_ddma = match trace {
                        Some(trace) => remote_dma::has_remote_traces(io, aux_mutex, trace.as_ptr() as u32),
                        None => false
                    };
                    #[cfg(not(has_drtio))]
                    let uses_ddma = false;
                    kern_send(io, &kern::DmaRetrieveReply {
                        trace:    trace,
                        duration: duration,
                        uses_ddma: uses_ddma,
                    })
                })
            }
            &kern::DmaStartRemoteRequest { id: _id, timestamp: _timestamp } => {
                #[cfg(has_drtio)]
                remote_dma::playback(io, aux_mutex, ddma_mutex, routing_table, _id as u32, _timestamp as u64);
                kern_acknowledge()
            }
            &kern::DmaAwaitRemoteRequest { id: _id } => {
                #[cfg(has_drtio)]
                let reply = match remote_dma::await_done(io, ddma_mutex, _id as u32, 10_000) {
                    Ok(remote_dma::RemoteState::PlaybackEnded { error, channel, timestamp }) =>
                        kern::DmaAwaitRemoteReply {
                            timeout: false,
                            error: error,
                            channel: channel,
                            timestamp: timestamp
                        },
                    _ => kern::DmaAwaitRemoteReply { timeout: true, error: 0, channel: 0, timestamp: 0},
                };
                #[cfg(not(has_drtio))]
                let reply = kern::DmaAwaitRemoteReply { timeout: false, error: 0, channel: 0, timestamp: 0};
                kern_send(io, &reply)
            }

            &kern::RpcSend { async, service, tag, data } => {
                match stream {
                    None => unexpected!("unexpected RPC in flash kernel"),
                    Some(ref mut stream) => {
                        host_write(stream, host::Reply::RpcRequest { async: async })?;
                        rpc::send_args(stream, service, tag, data)?;
                        if !async {
                            session.kernel_state = KernelState::RpcWait
                        }
                        kern_acknowledge()
                    }
                }
            },
            &kern::RpcFlush => {
                // See ksupport/lib.rs for the reason this request exists.
                // We do not need to do anything here because of how the main loop is
                // structured.
                kern_acknowledge()
            },

            &kern::CacheGetRequest { key } => {
                let value = session.congress.cache.get(key);
                kern_send(io, &kern::CacheGetReply {
                    // Zing! This transmute is only safe because we dynamically track
                    // whether the kernel has borrowed any values from the cache.
                    value: unsafe { mem::transmute(value) }
                })
            }

            &kern::CachePutRequest { key, value } => {
                let succeeded = session.congress.cache.put(key, value).is_ok();
                kern_send(io, &kern::CachePutReply { succeeded: succeeded })
            }

            &kern::RunFinished => {
                unsafe { kernel::stop() }
                session.kernel_state = KernelState::Absent;
                unsafe { session.congress.cache.unborrow() }

                match stream {
                    None => return Ok(true),
                    Some(ref mut stream) =>
                        host_write(stream, host::Reply::KernelFinished {
                            async_errors: unsafe { get_async_errors() }
                        }).map_err(|e| e.into())
                }
            }
            &kern::RunException {
                exceptions,
                stack_pointers,
                backtrace
            } => {
                unsafe { kernel::stop() }
                session.kernel_state = KernelState::Absent;
                unsafe { session.congress.cache.unborrow() }

                match stream {
                    None => {
                        error!("exception in flash kernel");
                        for exception in exceptions {
                            error!("{:?}", exception.unwrap());
                        }
                        return Ok(true)
                    },
                    Some(ref mut stream) => {
                        host_write(stream, host::Reply::KernelException {
                            exceptions: exceptions,
                            stack_pointers: stack_pointers,
                            backtrace: backtrace,
                            async_errors: unsafe { get_async_errors() }
                        }).map_err(|e| e.into())
                    }
                }
            }
            #[cfg(has_drtio)]
            &kern::SubkernelLoadRunRequest { id, run } => {
                let succeeded = match subkernel::load(
                    io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table, id, run) {
                        Ok(()) => true,
                        Err(e) => { error!("Error loading subkernel: {}", e); false }
                    };
                kern_send(io, &kern::SubkernelLoadRunReply { succeeded: succeeded })
            }
            #[cfg(has_drtio)]
            &kern::SubkernelAwaitFinishRequest{ optional_id, timeout } => {
                let res = subkernel::await_finish(io, subkernel_mutex, optional_id, timeout);
                kern_send(io, &kern::SubkernelAwaitFinishReply { timeout: res.is_err() })
            }
            #[cfg(has_drtio)]
            &kern::SubkernelMsgSend { id, tag, data } => {
                subkernel::message_send(io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table,
                    id, tag, data)?;
                kern_acknowledge()
            }
            #[cfg(has_drtio)]
            &kern::SubkernelMsgRecvRequest { id, timeout } => {
                let message_received = subkernel::message_await(io, subkernel_mutex, id, timeout);
                kern_send(io, &kern::SubkernelMsgRecvReply { timeout: message_received.is_err() })?;
                if let Ok((tag, data)) = message_received {
                    // receive code almost identical to RPC recv, except we are not reading from a stream
                    let mut reader = Cursor::new(data);
                    let mut tag: [u8; 1] = [tag];
                    loop {
                        // kernel has to consume all arguments in the whole message
                        let slot = kern_recv(io, |reply| {
                            match reply {
                                &kern::RpcRecvRequest(slot) => Ok(slot),
                                other => unexpected!(
                                    "expected root value slot from kernel CPU, not {:?}", other)
                            }
                        })?;
                        let res = rpc::recv_return(&mut reader, &tag, slot, &|size| -> Result<_, Error<SchedError>> {
                            if size == 0 {
                                return Ok(0 as *mut ())
                            }
                            kern_send(io, &kern::RpcRecvReply(Ok(size)))?;
                            Ok(kern_recv(io, |reply| {
                                match reply {
                                    &kern::RpcRecvRequest(slot) => Ok(slot),
                                    other => unexpected!(
                                        "expected nested value slot from kernel CPU, not {:?}", other)
                                }
                            })?)
                        });
                        match res {
                            Ok(_) => kern_send(io, &kern::RpcRecvReply(Ok(0)))?,
                            Err(_) => unexpected!("expected valid subkernel message data")
                        };
                        match reader.read_u8() {
                            Ok(t) => { tag[0] = t }, // update the tag for next read
                            Err(_) => break // reached the end of data, we're done
                        }
                    }
                    Ok(())
                } else {
                    // if timed out, no data has been received, exception should be raised by kernel
                    Ok(())
                }
            },

            request => unexpected!("unexpected request {:?} from kernel CPU", request)
        }.and(Ok(false))
    })
}

fn process_kern_queued_rpc(stream: &mut TcpStream,
                           _session: &mut Session) -> Result<(), Error<SchedError>> {
    rpc_queue::dequeue(|slice| {
        debug!("comm<-kern (async RPC)");
        let length = NativeEndian::read_u32(slice) as usize;
        host_write(stream, host::Reply::RpcRequest { async: true })?;
        debug!("{:?}", &slice[4..][..length]);
        stream.write_all(&slice[4..][..length])?;
        Ok(())
    })
}

fn host_kernel_worker(io: &Io, aux_mutex: &Mutex,
                      routing_table: &drtio_routing::RoutingTable,
                      up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
                      ddma_mutex: &Mutex, subkernel_mutex: &Mutex,
                      stream: &mut TcpStream,
                      congress: &mut Congress) -> Result<(), Error<SchedError>> {
    let mut session = Session::new(congress);

    loop {
        if stream.can_recv() {
            process_host_message(io, aux_mutex, ddma_mutex, subkernel_mutex,
                routing_table, stream, &mut session)?
        } else if !stream.may_recv() {
            return Ok(())
        }

        while !rpc_queue::empty() {
            process_kern_queued_rpc(stream, &mut session)?
        }

        #[cfg(has_drtio)]
        while let Some(subkernel_finished) = subkernel::get_finished_with_exception(
            io, aux_mutex, ddma_mutex, subkernel_mutex, routing_table)? {
            if subkernel_finished.comm_lost {
                error!("Communication with satellite lost while kernel {} was running", subkernel_finished.id);
            }
            if let Some(exception) = subkernel_finished.exception {
                stream.write_all(&exception)?;
            }
            
        }

        if mailbox::receive() != 0 {
            process_kern_message(io, aux_mutex,
                routing_table, up_destinations,
                ddma_mutex, subkernel_mutex,
                Some(stream), &mut session)?;
        }

        if session.kernel_state == KernelState::Running {
            if !rtio_clocking::crg::check() {
                host_write(stream, host::Reply::ClockFailure)?;
                return Err(Error::ClockFailure)
            }
        }

        io.relinquish()?
    }
}

fn flash_kernel_worker(io: &Io, aux_mutex: &Mutex,
                       routing_table: &drtio_routing::RoutingTable,
                       up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
                       ddma_mutex: &Mutex, subkernel_mutex: &Mutex, congress: &mut Congress,
                       config_key: &str) -> Result<(), Error<SchedError>> {
    let mut session = Session::new(congress);

    config::read(config_key, |result| {
        match result {
            Ok(kernel) => unsafe {
                // kernel CPU cannot access the SPI flash address space directly,
                // so make a copy.
                kern_load(io, &mut session, Vec::from(kernel).as_ref())
            },
            _ => Err(Error::KernelNotFound)
        }
    })?;
    kern_run(&mut session)?;

    loop {
        if !rpc_queue::empty() {
            unexpected!("unexpected background RPC in flash kernel")
        }

        if mailbox::receive() != 0 {
            if process_kern_message(io, aux_mutex, routing_table, up_destinations, ddma_mutex, subkernel_mutex, None, &mut session)? {
                return Ok(())
            }
        }

        if !rtio_clocking::crg::check() {
            return Err(Error::ClockFailure)
        }

        io.relinquish()?
    }
}

fn respawn<F>(io: &Io, handle: &mut Option<ThreadHandle>, f: F)
        where F: 'static + FnOnce(Io) + Send {
    match handle.take() {
        None => (),
        Some(handle) => {
            if !handle.terminated() {
                handle.interrupt();
                io.join(handle).expect("cannot join interrupt thread")
            }
        }
    }

    *handle = Some(io.spawn(16384, f))
}

pub fn thread(io: Io, aux_mutex: &Mutex,
        routing_table: &Urc<RefCell<drtio_routing::RoutingTable>>,
        up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
        ddma_mutex: &Mutex, subkernel_mutex: &Mutex) {
    let listener = TcpListener::new(&io, 65535);
    listener.listen(1381).expect("session: cannot listen");
    info!("accepting network sessions");

    let congress = Urc::new(RefCell::new(Congress::new()));

    let mut kernel_thread = None;
    {
        let routing_table = routing_table.borrow();
        let mut congress = congress.borrow_mut();
        info!("running startup kernel");
        match flash_kernel_worker(&io, &aux_mutex, &routing_table, &up_destinations, 
                ddma_mutex, subkernel_mutex, &mut congress, "startup_kernel") {
            Ok(()) =>
                info!("startup kernel finished"),
            Err(Error::KernelNotFound) =>
                info!("no startup kernel found"),
            Err(err) => {
                congress.finished_cleanly.set(false);
                error!("startup kernel aborted: {}", err);
            }
        }
    }

    loop {
        if listener.can_accept() {
            let mut stream = listener.accept().expect("session: cannot accept");
            stream.set_timeout(Some(2250));
            stream.set_keep_alive(Some(500));

            match host::read_magic(&mut stream) {
                Ok(()) => (),
                Err(_) => {
                    warn!("wrong magic from {}", stream.remote_endpoint());
                    stream.close().expect("session: cannot close");
                    continue
                }
            }
            match stream.write_all("e".as_bytes()) {
                Ok(()) => (),
                Err(_) => {
                    warn!("cannot send endian byte");
                    stream.close().expect("session: cannot close");
                    continue
                }
            }
            info!("new connection from {}", stream.remote_endpoint());

            let aux_mutex = aux_mutex.clone();
            let routing_table = routing_table.clone();
            let up_destinations = up_destinations.clone();
            let congress = congress.clone();
            let ddma_mutex = ddma_mutex.clone();
            let subkernel_mutex = subkernel_mutex.clone();
            let stream = stream.into_handle();
            respawn(&io, &mut kernel_thread, move |io| {
                let routing_table = routing_table.borrow();
                let mut congress = congress.borrow_mut();
                let mut stream = TcpStream::from_handle(&io, stream);
                match host_kernel_worker(&io, &aux_mutex, &routing_table, &up_destinations, 
                        &ddma_mutex, &subkernel_mutex, &mut stream, &mut *congress) {
                    Ok(()) => (),
                    Err(Error::Protocol(host::Error::Io(IoError::UnexpectedEnd))) =>
                        info!("connection closed"),
                    Err(Error::Protocol(host::Error::Io(
                            IoError::Other(SchedError::Interrupted)))) =>
                        info!("kernel interrupted"),
                    Err(err) => {
                        congress.finished_cleanly.set(false);
                        error!("session aborted: {}", err);
                    }
                }
                stream.close().expect("session: close socket");
            });
        }

        if kernel_thread.as_ref().map_or(true, |h| h.terminated()) {
            info!("no connection, starting idle kernel");

            let aux_mutex = aux_mutex.clone();
            let routing_table = routing_table.clone();
            let up_destinations = up_destinations.clone();
            let congress = congress.clone();
            let ddma_mutex = ddma_mutex.clone();
            let subkernel_mutex = subkernel_mutex.clone();
            respawn(&io, &mut kernel_thread, move |io| {
                let routing_table = routing_table.borrow();
                let mut congress = congress.borrow_mut();
                match flash_kernel_worker(&io, &aux_mutex, &routing_table, &up_destinations, 
                    &ddma_mutex, &subkernel_mutex, &mut *congress, "idle_kernel") {
                    Ok(()) =>
                        info!("idle kernel finished, standing by"),
                    Err(Error::Protocol(host::Error::Io(
                            IoError::Other(SchedError::Interrupted)))) =>
                        info!("idle kernel interrupted"),
                    Err(Error::KernelNotFound) => {
                        info!("no idle kernel found");
                        while io.relinquish().is_ok() {}
                    }
                    Err(err) =>
                        error!("idle kernel aborted: {}", err)
                }
            })
        }

        let _ = io.relinquish();
    }
}
