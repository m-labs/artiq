use std::prelude::v1::*;
use std::{mem, str};
use std::cell::{Cell, RefCell};
use std::io::{self, Read, Write};
use std::error::Error;
use {config, rtio_mgt, mailbox, rpc_queue, kernel};
use cache::Cache;
use rtio_dma::Manager as DmaManager;
use urc::Urc;
use sched::{ThreadHandle, Io};
use sched::{TcpListener, TcpStream};
use byteorder::{ByteOrder, NetworkEndian};
use board;

use rpc_proto as rpc;
use session_proto as host;
use kernel_proto as kern;
use kern_hwreq;

macro_rules! unexpected {
    ($($arg:tt)*) => {
        {
            error!($($arg)*);
            return Err(io::Error::new(io::ErrorKind::InvalidData, "protocol error"))
        }
    };
}

fn io_error(msg: &str) -> io::Error {
    io::Error::new(io::ErrorKind::Other, msg)
}

// Persistent state
#[derive(Debug)]
struct Congress {
    now: u64,
    cache: Cache,
    dma_manager: DmaManager,
    finished_cleanly: Cell<bool>
}

impl Congress {
    fn new() -> Congress {
        Congress {
            now: 0,
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
    watchdog_set: board::clock::WatchdogSet,
    log_buffer: String
}

impl<'a> Session<'a> {
    fn new(congress: &mut Congress) -> Session {
        Session {
            congress: congress,
            kernel_state: KernelState::Absent,
            watchdog_set: board::clock::WatchdogSet::new(),
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

fn check_magic(stream: &mut TcpStream) -> io::Result<()> {
    const MAGIC: &'static [u8] = b"ARTIQ coredev\n";

    let mut magic: [u8; 14] = [0; 14];
    stream.read_exact(&mut magic)?;
    if magic != MAGIC {
        Err(io::Error::new(io::ErrorKind::InvalidData, "unrecognized magic"))
    } else {
        Ok(())
    }
}

fn host_read(stream: &mut TcpStream) -> io::Result<host::Request> {
    let request = host::Request::read_from(stream)?;
    match &request {
        &host::Request::LoadKernel(_) => debug!("comm<-host LoadLibrary(...)"),
        _ => debug!("comm<-host {:?}", request)
    }
    Ok(request)
}

fn host_write(stream: &mut Write, reply: host::Reply) -> io::Result<()> {
    debug!("comm->host {:?}", reply);
    reply.write_to(stream)
}

pub fn kern_send(io: &Io, request: &kern::Message) -> io::Result<()> {
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
    io.until(mailbox::acknowledged)
}

fn kern_recv_notrace<R, F>(io: &Io, f: F) -> io::Result<R>
        where F: FnOnce(&kern::Message) -> io::Result<R> {
    io.until(|| mailbox::receive() != 0)?;
    if !kernel::validate(mailbox::receive()) {
        let message = format!("invalid kernel CPU pointer 0x{:x}", mailbox::receive());
        return Err(io::Error::new(io::ErrorKind::InvalidData, message))
    }

    f(unsafe { mem::transmute::<usize, &kern::Message>(mailbox::receive()) })
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
fn kern_recv<R, F>(io: &Io, f: F) -> io::Result<R>
        where F: FnOnce(&kern::Message) -> io::Result<R> {
    kern_recv_notrace(io, |reply| {
        kern_recv_dotrace(reply);
        f(reply)
    })
}

pub fn kern_acknowledge() -> io::Result<()> {
    mailbox::acknowledge();
    Ok(())
}

unsafe fn kern_load(io: &Io, session: &mut Session, library: &[u8]) -> io::Result<()> {
    if session.running() {
        unexpected!("attempted to load a new kernel while a kernel was running")
    }

    kernel::start();

    kern_send(io, &kern::LoadRequest(&library))?;
    kern_recv(io, |reply| {
        match reply {
            &kern::LoadReply(Ok(())) => {
                session.kernel_state = KernelState::Loaded;
                Ok(())
            }
            &kern::LoadReply(Err(ref error)) => {
                kernel::stop();
                Err(io::Error::new(io::ErrorKind::Other,
                                   format!("cannot load kernel: {}", error)))
            }
            other =>
                unexpected!("unexpected reply from kernel CPU: {:?}", other)
        }
    })
}

fn kern_run(session: &mut Session) -> io::Result<()> {
    if session.kernel_state != KernelState::Loaded {
        unexpected!("attempted to run a kernel while not in Loaded state")
    }

    session.kernel_state = KernelState::Running;
    // TODO: make this a separate request
    kern_acknowledge()
}

fn process_host_message(io: &Io,
                        stream: &mut TcpStream,
                        session: &mut Session) -> io::Result<()> {
    match host_read(stream)? {
        host::Request::SystemInfo => {
            host_write(stream, host::Reply::SystemInfo {
                ident: board::ident(&mut [0; 64]),
                finished_cleanly: session.congress.finished_cleanly.get()
            })?;
            session.congress.finished_cleanly.set(true);
            Ok(())
        }

        // artiq_coreconfig
        host::Request::FlashRead { ref key } => {
            config::read(key, |result| {
                match result {
                    Ok(value) => host_write(stream, host::Reply::FlashRead(&value)),
                    Err(())   => host_write(stream, host::Reply::FlashError)
                }
            })
        }

        host::Request::FlashWrite { ref key, ref value } => {
            match config::write(key, value) {
                Ok(_)  => host_write(stream, host::Reply::FlashOk),
                Err(_) => host_write(stream, host::Reply::FlashError)
            }
        }

        host::Request::FlashRemove { ref key } => {
            match config::remove(key) {
                Ok(()) => host_write(stream, host::Reply::FlashOk),
                Err(_) => host_write(stream, host::Reply::FlashError),
            }

        }

        host::Request::FlashErase => {
            match config::erase() {
                Ok(()) => host_write(stream, host::Reply::FlashOk),
                Err(_) => host_write(stream, host::Reply::FlashError),
            }
        }

        // artiq_run/artiq_master
        host::Request::SwitchClock(clk) => {
            if session.running() {
                unexpected!("attempted to switch RTIO clock while a kernel was running")
            }

            if rtio_mgt::crg::switch_clock(clk) {
                host_write(stream, host::Reply::ClockSwitchCompleted)
            } else {
                host_write(stream, host::Reply::ClockSwitchFailed)
            }
        }

        host::Request::LoadKernel(kernel) =>
            match unsafe { kern_load(io, session, &kernel) } {
                Ok(()) => host_write(stream, host::Reply::LoadCompleted),
                Err(error) => {
                    host_write(stream, host::Reply::LoadFailed(error.description()))?;
                    kern_acknowledge()
                }
            },

        host::Request::RunKernel =>
            match kern_run(session) {
                Ok(()) => Ok(()),
                Err(_) => host_write(stream, host::Reply::KernelStartupFailed)
            },

        host::Request::RpcReply { tag } => {
            if session.kernel_state != KernelState::RpcWait {
                unexpected!("unsolicited RPC reply")
            }

            let slot = kern_recv(io, |reply| {
                match reply {
                    &kern::RpcRecvRequest(slot) => Ok(slot),
                    other => unexpected!("unexpected reply from kernel CPU: {:?}", other)
                }
            })?;
            rpc::recv_return(stream, &tag, slot, &|size| {
                kern_send(io, &kern::RpcRecvReply(Ok(size)))?;
                kern_recv(io, |reply| {
                    match reply {
                        &kern::RpcRecvRequest(slot) => Ok(slot),
                        other => unexpected!("unexpected reply from kernel CPU: {:?}", other)
                    }
                })
            })?;
            kern_send(io, &kern::RpcRecvReply(Ok(0)))?;

            session.kernel_state = KernelState::Running;
            Ok(())
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
                    other =>
                        unexpected!("unexpected reply from kernel CPU: {:?}", other)
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

            session.kernel_state = KernelState::Running;
            Ok(())
        }
    }
}

fn process_kern_message(io: &Io, mut stream: Option<&mut TcpStream>,
                        session: &mut Session) -> io::Result<bool> {
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
        if kern_hwreq::process_kern_hwreq(io, request)? {
            return Ok(false)
        }
        match request {
            &kern::Log(args) => {
                use std::fmt::Write;
                session.log_buffer.write_fmt(args)
                       .map_err(|_| io_error("cannot append to session log buffer"))?;
                session.flush_log_buffer();
                kern_acknowledge()
            }

            &kern::LogSlice(arg) => {
                session.log_buffer += arg;
                session.flush_log_buffer();
                kern_acknowledge()
            }

            &kern::NowInitRequest =>
                kern_send(io, &kern::NowInitReply(session.congress.now)),

            &kern::NowSave(now) => {
                session.congress.now = now;
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
                board::cache::flush_l2_cache();
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
                let id = session.watchdog_set.set_ms(ms)
                                .map_err(|()| io_error("out of watchdogs"))?;
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
            }

            &kern::CacheGetRequest { key } => {
                let value = session.congress.cache.get(key);
                kern_send(io, &kern::CacheGetReply {
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
                        host_write(stream, host::Reply::KernelFinished)
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
                        })
                    }
                }
            }

            request => unexpected!("unexpected request {:?} from kernel CPU", request)
        }.and(Ok(false))
    })
}

fn process_kern_queued_rpc(stream: &mut TcpStream,
                           _session: &mut Session) -> io::Result<()> {
    rpc_queue::dequeue(|slice| {
        debug!("comm<-kern (async RPC)");
        let length = NetworkEndian::read_u32(slice) as usize;
        host_write(stream, host::Reply::RpcRequest { async: true })?;
        debug!("{:?}", &slice[4..][..length]);
        stream.write(&slice[4..][..length])?;
        Ok(())
    })
}

fn host_kernel_worker(io: &Io,
                      stream: &mut TcpStream,
                      congress: &mut Congress) -> io::Result<()> {
    let mut session = Session::new(congress);

    loop {
        while !rpc_queue::empty() {
            process_kern_queued_rpc(stream, &mut session)?
        }

        if stream.can_recv() {
            process_host_message(io, stream, &mut session)?
        } else if !stream.may_recv() {
            return Ok(())
        }

        if mailbox::receive() != 0 {
            process_kern_message(io, Some(stream), &mut session)?;
        }

        if session.kernel_state == KernelState::Running {
            if session.watchdog_set.expired() {
                host_write(stream, host::Reply::WatchdogExpired)?;
                return Err(io_error("watchdog expired"))
            }

            if !rtio_mgt::crg::check() {
                host_write(stream, host::Reply::ClockFailure)?;
                return Err(io_error("RTIO clock failure"))
            }
        }

        io.relinquish()?
    }
}

fn flash_kernel_worker(io: &Io,
                       congress: &mut Congress,
                       config_key: &str) -> io::Result<()> {
    let mut session = Session::new(congress);

    config::read(config_key, |result| {
        match result {
            Ok(kernel) if kernel.len() > 0 => unsafe {
                // kernel CPU cannot access the SPI flash address space directly,
                // so make a copy.
                kern_load(io, &mut session, Vec::from(kernel).as_ref())
            },
            _ => Err(io::Error::new(io::ErrorKind::NotFound, "kernel not found")),
        }
    })?;
    kern_run(&mut session)?;

    loop {
        if !rpc_queue::empty() {
            return Err(io_error("unexpected background RPC in flash kernel"))
        }

        if mailbox::receive() != 0 {
            if process_kern_message(io, None, &mut session)? {
                return Ok(())
            }
        }

        if session.watchdog_set.expired() {
            return Err(io_error("watchdog expired"))
        }

        if !rtio_mgt::crg::check() {
            return Err(io_error("RTIO clock failure"))
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

pub fn thread(io: Io) {
    let listener = TcpListener::new(&io, 65535);
    listener.listen(1381).expect("session: cannot listen");
    info!("accepting network sessions");

    let congress = Urc::new(RefCell::new(Congress::new()));

    let mut kernel_thread = None;
    {
        let congress = congress.clone();
        respawn(&io, &mut kernel_thread, move |io| {
            let mut congress = borrow_mut!(congress);
            info!("running startup kernel");
            match flash_kernel_worker(&io, &mut congress, "startup_kernel") {
                Ok(()) => info!("startup kernel finished"),
                Err(err) => {
                    if err.kind() == io::ErrorKind::NotFound {
                        info!("no startup kernel found")
                    } else {
                        congress.finished_cleanly.set(false);
                        error!("startup kernel aborted: {}", err);
                    }
                }
            }
        })
    }

    loop {
        if listener.can_accept() {
            let mut stream = listener.accept().expect("session: cannot accept");
            match check_magic(&mut stream) {
                Ok(()) => (),
                Err(_) => {
                    warn!("wrong magic from {}", stream.remote_endpoint());
                    stream.close().expect("session: cannot close");
                    continue
                }
            }
            info!("new connection from {}", stream.remote_endpoint());

            let congress = congress.clone();
            let stream = stream.into_handle();
            respawn(&io, &mut kernel_thread, move |io| {
                let mut congress = borrow_mut!(congress);
                let mut stream = TcpStream::from_handle(&io, stream);
                match host_kernel_worker(&io, &mut stream, &mut *congress) {
                    Ok(()) => (),
                    Err(err) => {
                        if err.kind() == io::ErrorKind::UnexpectedEof {
                            info!("connection closed");
                        } else if err.kind() == io::ErrorKind::Interrupted {
                            info!("kernel interrupted");
                        } else {
                            congress.finished_cleanly.set(false);
                            error!("session aborted: {}", err);
                        }
                    }
                }
            });
        }

        if kernel_thread.as_ref().map_or(true, |h| h.terminated()) {
            info!("no connection, starting idle kernel");

            let congress = congress.clone();
            respawn(&io, &mut kernel_thread, move |io| {
                let mut congress = borrow_mut!(congress);
                match flash_kernel_worker(&io, &mut *congress, "idle_kernel") {
                    Ok(()) =>
                        info!("idle kernel finished, standing by"),
                    Err(err) => {
                        if err.kind() == io::ErrorKind::Interrupted {
                            info!("idle kernel interrupted");
                        } else if err.kind() == io::ErrorKind::NotFound {
                            info!("no idle kernel found");
                            while io.relinquish().is_ok() {}
                        } else {
                            error!("idle kernel aborted: {}", err);
                        }
                    }
                }
            })
        }

        let _ = io.relinquish();
    }
}
