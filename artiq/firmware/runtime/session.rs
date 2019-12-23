use core::{mem, str, cell::{Cell, RefCell}, fmt::Write as FmtWrite};
use alloc::{Vec, String};
use byteorder::{ByteOrder, NetworkEndian};

use io::{Read, Write, Error as IoError};
use board_misoc::{ident, cache, config};
use {mailbox, rpc_queue, kernel};
use urc::Urc;
use sched::{ThreadHandle, Io, Mutex, TcpListener, TcpStream, Error as SchedError};
use rtio_clocking;
use rtio_dma::Manager as DmaManager;
use cache::Cache;
use kern_hwreq;
use watchdog::WatchdogSet;
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
    #[fail(display = "watchdog {} expired", _0)]
    WatchdogExpired(usize),
    #[fail(display = "out of watchdogs")]
    OutOfWatchdogs,
    #[fail(display = "protocol error: {}", _0)]
    Protocol(#[cause] host::Error<T>),
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
    watchdog_set: WatchdogSet,
    log_buffer: String
}

impl<'a> Session<'a> {
    fn new(congress: &mut Congress) -> Session {
        Session {
            congress: congress,
            kernel_state: KernelState::Absent,
            watchdog_set: WatchdogSet::new(),
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
        &kern::DmaRetrieveReply { trace, duration } => {
            if trace.map(|data| data.len() > 100).unwrap_or(false) {
                debug!("comm->kern DmaRetrieveReply {{ trace: ..., duration: {:?} }}", duration)
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

fn process_host_message(io: &Io,
                        stream: &mut TcpStream,
                        session: &mut Session) -> Result<(), Error<SchedError>> {
    match host_read(stream)? {
        host::Request::SystemInfo => {
            host_write(stream, host::Reply::SystemInfo {
                ident: ident::read(&mut [0; 64]),
                finished_cleanly: session.congress.finished_cleanly.get()
            })?;
            session.congress.finished_cleanly.set(true)
        }

        host::Request::LoadKernel(kernel) =>
            match unsafe { kern_load(io, session, &kernel) } {
                Ok(()) => host_write(stream, host::Reply::LoadCompleted)?,
                Err(error) => {
                    let mut description = String::new();
                    write!(&mut description, "{}", error).unwrap();
                    host_write(stream, host::Reply::LoadFailed(&description))?;
                    kern_acknowledge()?;
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
            name, message, param, file, line, column, function
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

            let exn = kern::Exception {
                name:     name.as_ref(),
                message:  message.as_ref(),
                param:    param,
                file:     file.as_ref(),
                line:     line,
                column:   column,
                function: function.as_ref()
            };
            kern_send(io, &kern::RpcRecvReply(Err(exn)))?;

            session.kernel_state = KernelState::Running
        }
    }

    Ok(())
}

fn process_kern_message(io: &Io, aux_mutex: &Mutex,
                        routing_table: &drtio_routing::RoutingTable,
                        up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
                        mut stream: Option<&mut TcpStream>,
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
                session.congress.dma_manager.record_start(name);
                kern_acknowledge()
            }
            &kern::DmaRecordAppend(data) => {
                session.congress.dma_manager.record_append(data);
                kern_acknowledge()
            }
            &kern::DmaRecordStop { duration } => {
                session.congress.dma_manager.record_stop(duration);
                cache::flush_l2_cache();
                kern_acknowledge()
            }
            &kern::DmaEraseRequest { name } => {
                session.congress.dma_manager.erase(name);
                kern_acknowledge()
            }
            &kern::DmaRetrieveRequest { name } => {
                session.congress.dma_manager.with_trace(name, |trace, duration| {
                    kern_send(io, &kern::DmaRetrieveReply {
                        trace:    trace,
                        duration: duration
                    })
                })
            }

            &kern::WatchdogSetRequest { ms } => {
                let id = session.watchdog_set.set_ms(ms).map_err(|()| Error::OutOfWatchdogs)?;
                kern_send(io, &kern::WatchdogSetReply { id: id })
            }
            &kern::WatchdogClear { id } => {
                session.watchdog_set.clear(id);
                kern_acknowledge()
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
                    value: unsafe { mem::transmute::<*const [i32], &'static [i32]>(value) }
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
                        host_write(stream, host::Reply::KernelFinished).map_err(|e| e.into())
                }
            }
            &kern::RunException {
                exception: kern::Exception { name, message, param, file, line, column, function },
                backtrace
            } => {
                unsafe { kernel::stop() }
                session.kernel_state = KernelState::Absent;
                unsafe { session.congress.cache.unborrow() }

                match stream {
                    None => {
                        error!("exception in flash kernel");
                        error!("{}: {} {:?}", name, message, param);
                        error!("at {}:{}:{} in {}", file, line, column, function);
                        return Ok(true)
                    },
                    Some(ref mut stream) => {
                        host_write(stream, host::Reply::KernelException {
                            name:      name,
                            message:   message,
                            param:     param,
                            file:      file,
                            line:      line,
                            column:    column,
                            function:  function,
                            backtrace: backtrace
                        }).map_err(|e| e.into())
                    }
                }
            }

            request => unexpected!("unexpected request {:?} from kernel CPU", request)
        }.and(Ok(false))
    })
}

fn process_kern_queued_rpc(stream: &mut TcpStream,
                           _session: &mut Session) -> Result<(), Error<SchedError>> {
    rpc_queue::dequeue(|slice| {
        debug!("comm<-kern (async RPC)");
        let length = NetworkEndian::read_u32(slice) as usize;
        host_write(stream, host::Reply::RpcRequest { async: true })?;
        debug!("{:?}", &slice[4..][..length]);
        stream.write_all(&slice[4..][..length])?;
        Ok(())
    })
}

fn host_kernel_worker(io: &Io, aux_mutex: &Mutex,
                      routing_table: &drtio_routing::RoutingTable,
                      up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>,
                      stream: &mut TcpStream,
                      congress: &mut Congress) -> Result<(), Error<SchedError>> {
    let mut session = Session::new(congress);

    loop {
        if stream.can_recv() {
            process_host_message(io, stream, &mut session)?
        } else if !stream.may_recv() {
            return Ok(())
        }

        while !rpc_queue::empty() {
            process_kern_queued_rpc(stream, &mut session)?
        }

        if mailbox::receive() != 0 {
            process_kern_message(io, aux_mutex,
                routing_table, up_destinations,
                Some(stream), &mut session)?;
        }

        if session.kernel_state == KernelState::Running {
            if let Some(idx) = session.watchdog_set.expired() {
                host_write(stream, host::Reply::WatchdogExpired)?;
                return Err(Error::WatchdogExpired(idx))
            }

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
                       congress: &mut Congress,
                       config_key: &str) -> Result<(), Error<SchedError>> {
    let mut session = Session::new(congress);

    config::read(config_key, |result| {
        match result {
            Ok(kernel) if kernel.len() > 0 => unsafe {
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
            if process_kern_message(io, aux_mutex, routing_table, up_destinations, None, &mut session)? {
                return Ok(())
            }
        }

        if let Some(idx) = session.watchdog_set.expired() {
            return Err(Error::WatchdogExpired(idx))
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
        up_destinations: &Urc<RefCell<[bool; drtio_routing::DEST_COUNT]>>) {
    let listener = TcpListener::new(&io, 65535);
    listener.listen(1381).expect("session: cannot listen");
    info!("accepting network sessions");

    let congress = Urc::new(RefCell::new(Congress::new()));

    let mut kernel_thread = None;
    {
        let aux_mutex = aux_mutex.clone();
        let routing_table = routing_table.clone();
        let up_destinations = up_destinations.clone();
        let congress = congress.clone();
        respawn(&io, &mut kernel_thread, move |io| {
            let routing_table = routing_table.borrow();
            let mut congress = congress.borrow_mut();
            info!("running startup kernel");
            match flash_kernel_worker(&io, &aux_mutex, &routing_table, &up_destinations, &mut congress, "startup_kernel") {
                Ok(()) =>
                    info!("startup kernel finished"),
                Err(Error::KernelNotFound) =>
                    info!("no startup kernel found"),
                Err(err) => {
                    congress.finished_cleanly.set(false);
                    error!("startup kernel aborted: {}", err);
                }
            }
        })
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
            info!("new connection from {}", stream.remote_endpoint());

            let aux_mutex = aux_mutex.clone();
            let routing_table = routing_table.clone();
            let up_destinations = up_destinations.clone();
            let congress = congress.clone();
            let stream = stream.into_handle();
            respawn(&io, &mut kernel_thread, move |io| {
                let routing_table = routing_table.borrow();
                let mut congress = congress.borrow_mut();
                let mut stream = TcpStream::from_handle(&io, stream);
                match host_kernel_worker(&io, &aux_mutex, &routing_table, &up_destinations, &mut stream, &mut *congress) {
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
            });
        }

        if kernel_thread.as_ref().map_or(true, |h| h.terminated()) {
            info!("no connection, starting idle kernel");

            let aux_mutex = aux_mutex.clone();
            let routing_table = routing_table.clone();
            let up_destinations = up_destinations.clone();
            let congress = congress.clone();
            respawn(&io, &mut kernel_thread, move |io| {
                let routing_table = routing_table.borrow();
                let mut congress = congress.borrow_mut();
                match flash_kernel_worker(&io, &aux_mutex, &routing_table, &up_destinations, &mut *congress, "idle_kernel") {
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
