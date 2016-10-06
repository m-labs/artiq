use std::prelude::v1::*;
use std::{mem, str};
use std::cell::RefCell;
use std::io::{self, Read};
use {config, rtio_crg, clock, mailbox, kernel};
use logger::BufferLogger;
use cache::Cache;
use urc::Urc;
use sched::{ThreadHandle, Waiter, Spawner};
use sched::{TcpListener, TcpStream, SocketAddr, IP_ANY};

use rpc;
use session_proto as host;
use kernel_proto as kern;

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
    cache: Cache
}

impl Congress {
    fn new() -> Congress {
        Congress {
            now: 0,
            cache: Cache::new()
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
    watchdog_set: clock::WatchdogSet,
    log_buffer: String
}

impl<'a> Session<'a> {
    fn new(congress: &mut Congress) -> Session {
        Session {
            congress: congress,
            kernel_state: KernelState::Absent,
            watchdog_set: clock::WatchdogSet::new(),
            log_buffer: String::new()
        }
    }

    fn running(&self) -> bool {
        match self.kernel_state {
            KernelState::Absent  | KernelState::Loaded  => false,
            KernelState::Running | KernelState::RpcWait => true
        }
    }
}

impl<'a> Drop for Session<'a> {
    fn drop(&mut self) {
        kernel::stop()
    }
}

fn check_magic(stream: &mut TcpStream) -> io::Result<()> {
    const MAGIC: &'static [u8] = b"ARTIQ coredev\n";

    let mut magic: [u8; 14] = [0; 14];
    try!(stream.read_exact(&mut magic));
    if magic != MAGIC {
        Err(io::Error::new(io::ErrorKind::InvalidData, "unrecognized magic"))
    } else {
        Ok(())
    }
}

fn host_read(stream: &mut TcpStream) -> io::Result<host::Request> {
    let request = try!(host::Request::read_from(stream));
    match &request {
        &host::Request::LoadKernel(_) => trace!("comm<-host LoadLibrary(...)"),
        _ => trace!("comm<-host {:?}", request)
    }
    Ok(request)
}

fn host_write(stream: &mut TcpStream, reply: host::Reply) -> io::Result<()> {
    trace!("comm->host {:?}", reply);
    reply.write_to(stream)
}

fn kern_send<'a>(waiter: Waiter, request: kern::Message<'a>) -> io::Result<()> {
    match &request {
        &kern::LoadRequest(_) => trace!("comm->kern LoadRequest(...)"),
        _ => trace!("comm->kern {:?}", request)
    }
    request.send_and_wait(waiter)
}

fn kern_recv<R, F>(waiter: Waiter, f: F) -> io::Result<R>
        where F: FnOnce(kern::Message) -> io::Result<R> {
    kern::Message::wait_and_receive(waiter, |reply| {
        trace!("comm<-kern {:?}", reply);
        f(reply)
    })
}

fn kern_acknowledge() -> io::Result<()> {
    kern::Message::acknowledge();
    Ok(())
}

unsafe fn kern_load(waiter: Waiter, session: &mut Session, library: &[u8]) -> io::Result<()> {
    if session.running() {
        unexpected!("attempted to load a new kernel while a kernel was running")
    }

    kernel::start();

    try!(kern_send(waiter, kern::LoadRequest(&library)));
    kern_recv(waiter, |reply| {
        match reply {
            kern::LoadReply { error: None } => {
                session.kernel_state = KernelState::Loaded;
                Ok(())
            }
            kern::LoadReply { error: Some(cause) } =>
                unexpected!("cannot load kernel: {}", cause),
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

fn process_host_message(waiter: Waiter,
                        stream: &mut TcpStream,
                        session: &mut Session) -> io::Result<()> {
    match try!(host_read(stream)) {
        host::Request::Ident =>
            host_write(stream, host::Reply::Ident(::board::ident(&mut [0; 64]))),

        // artiq_corelog
        host::Request::Log => {
            // Logging the packet with the log is inadvisable
            trace!("comm->host Log(...)");
            BufferLogger::with_instance(|logger| {
                logger.extract(|log| {
                    host::Reply::Log(log).write_to(stream)
                })
            })
        }

        host::Request::LogClear => {
            BufferLogger::with_instance(|logger| logger.clear());
            host_write(stream, host::Reply::Log(""))
        }

        // artiq_coreconfig
        host::Request::FlashRead { ref key } => {
            let value = config::read_to_end(key);
            host_write(stream, host::Reply::FlashRead(&value))
        }

        host::Request::FlashWrite { ref key, ref value } => {
            match config::write(key, value) {
                Ok(_)  => host_write(stream, host::Reply::FlashOk),
                Err(_) => host_write(stream, host::Reply::FlashError)
            }
        }

        host::Request::FlashRemove { ref key } => {
            config::remove(key);
            host_write(stream, host::Reply::FlashOk)
        }

        host::Request::FlashErase => {
            config::erase();
            host_write(stream, host::Reply::FlashOk)
        }

        // artiq_run/artiq_master
        host::Request::SwitchClock(clk) => {
            if session.running() {
                unexpected!("attempted to switch RTIO clock while a kernel was running")
            }

            if rtio_crg::switch_clock(clk) {
                host_write(stream, host::Reply::ClockSwitchCompleted)
            } else {
                host_write(stream, host::Reply::ClockSwitchFailed)
            }
        }

        host::Request::LoadKernel(kernel) =>
            match unsafe { kern_load(waiter, session, &kernel) } {
                Ok(()) => host_write(stream, host::Reply::LoadCompleted),
                Err(_) => host_write(stream, host::Reply::LoadFailed)
            },

        host::Request::RunKernel =>
            match kern_run(session) {
                Ok(()) => Ok(()),
                Err(_) => host_write(stream, host::Reply::KernelStartupFailed)
            },

        host::Request::RpcReply { tag, data } => {
            if session.kernel_state != KernelState::RpcWait {
                unexpected!("unsolicited RPC reply")
            }

            try!(kern_recv(waiter, |reply| {
                match reply {
                    kern::RpcRecvRequest { slot } => {
                        let mut data = io::Cursor::new(data);
                        rpc::recv_return(&mut data, &tag, slot, &|size| {
                            try!(kern_send(waiter, kern::RpcRecvReply {
                                alloc_size: size, exception: None
                            }));
                            kern_recv(waiter, |reply| {
                                match reply {
                                    kern::RpcRecvRequest { slot } => Ok(slot),
                                    _ => unreachable!()
                                }
                            })
                        })
                    }
                    other =>
                        unexpected!("unexpected reply from kernel CPU: {:?}", other)
                }
            }));
            try!(kern_send(waiter, kern::RpcRecvReply { alloc_size: 0, exception: None }));

            session.kernel_state = KernelState::Running;
            Ok(())
        }

        host::Request::RpcException {
            name, message, param, file, line, column, function
        } => {
            if session.kernel_state != KernelState::RpcWait {
                unexpected!("unsolicited RPC reply")
            }

            try!(kern_recv(waiter, |reply| {
                match reply {
                    kern::RpcRecvRequest { .. } => Ok(()),
                    other =>
                        unexpected!("unexpected reply from kernel CPU: {:?}", other)
                }
            }));
            try!(kern_send(waiter, kern::RpcRecvReply {
                alloc_size: 0,
                exception: Some(kern::Exception {
                    name: &name,
                    message: &message,
                    param: param,
                    file: &file,
                    line: line,
                    column: column,
                    function: &function
                })
            }));

            session.kernel_state = KernelState::Running;
            Ok(())
        }
    }
}

fn process_kern_message(waiter: Waiter,
                        mut stream: Option<&mut TcpStream>,
                        session: &mut Session) -> io::Result<bool> {
    kern::Message::wait_and_receive(waiter, |request| {
        match (&request, session.kernel_state) {
            (&kern::LoadReply { .. }, KernelState::Loaded) |
            (&kern::RpcRecvRequest { .. }, KernelState::RpcWait) => {
                // We're standing by; ignore the message.
                return Ok(false)
            }
            (_, KernelState::Running) => (),
            _ => {
                unexpected!("unexpected request {:?} from kernel CPU in {:?} state",
                            request, session.kernel_state)
            }
        }

        trace!("comm<-kern {:?}", request);
        match request {
            kern::Log(log) => {
                session.log_buffer += log;
                try!(kern_acknowledge());

                if &log[log.len() - 1..] == "\n" {
                    for line in session.log_buffer.lines() {
                        info!(target: "kernel", "{}", line);
                    }
                    session.log_buffer.clear()
                }
                Ok(())
            }

            kern::NowInitRequest =>
                kern_send(waiter, kern::NowInitReply(session.congress.now)),

            kern::NowSave(now) => {
                session.congress.now = now;
                kern_acknowledge()
            }

            kern::WatchdogSetRequest { ms } => {
                let id = try!(session.watchdog_set.set_ms(ms)
                                .map_err(|()| io_error("out of watchdogs")));
                kern_send(waiter, kern::WatchdogSetReply { id: id })
            }

            kern::WatchdogClear { id } => {
                session.watchdog_set.clear(id);
                kern_acknowledge()
            }

            kern::RpcSend { service, batch, tag, data } => {
                match stream {
                    None => unexpected!("unexpected RPC in flash kernel"),
                    Some(ref mut stream) => {
                        let mut buf = Vec::new();
                        try!(rpc::send_args(&mut buf, tag, data));
                        try!(host_write(stream, host::Reply::RpcRequest {
                            service: service,
                            data: &buf[..]
                        }));
                        if !batch {
                            session.kernel_state = KernelState::RpcWait
                        }
                        kern_acknowledge()
                    }
                }
            }

            kern::CacheGetRequest { key } => {
                let value = session.congress.cache.get(key);
                kern_send(waiter, kern::CacheGetReply {
                    value: unsafe { mem::transmute::<*const [u32], &'static [u32]>(value) }
                })
            }

            kern::CachePutRequest { key, value } => {
                let succeeded = session.congress.cache.put(key, value).is_ok();
                kern_send(waiter, kern::CachePutReply { succeeded: succeeded })
            }

            kern::RunFinished => {
                kernel::stop();
                session.kernel_state = KernelState::Absent;

                match stream {
                    None => return Ok(true),
                    Some(ref mut stream) =>
                        host_write(stream, host::Reply::KernelFinished)
                }
            }

            kern::RunException { exception: ref exn, backtrace } => {
                kernel::stop();
                session.kernel_state = KernelState::Absent;

                match stream {
                    None => {
                        error!("exception in flash kernel");
                        error!("{}: {} {:?}", exn.name, exn.message, exn.param);
                        error!("at {}:{}:{} in {}", exn.file, exn.line, exn.column, exn.function);
                        return Ok(true)
                    },
                    Some(ref mut stream) =>
                        host_write(stream, host::Reply::KernelException {
                            name: exn.name,
                            message: exn.message,
                            param: exn.param,
                            file: exn.file,
                            line: exn.line,
                            column: exn.column,
                            function: exn.function,
                            backtrace: backtrace
                        })
                }
            }

            request => unexpected!("unexpected request {:?} from kernel CPU", request)
        }.and(Ok(false))
    })
}

fn host_kernel_worker(waiter: Waiter,
                      stream: &mut TcpStream,
                      congress: &mut Congress) -> io::Result<()> {
    let mut session = Session::new(congress);

    loop {
        if stream.readable() {
            try!(process_host_message(waiter, stream, &mut session));
        }

        if mailbox::receive() != 0 {
            try!(process_kern_message(waiter, Some(stream), &mut session));
        }

        if session.kernel_state == KernelState::Running {
            if session.watchdog_set.expired() {
                try!(host_write(stream, host::Reply::WatchdogExpired));
                return Err(io_error("watchdog expired"))
            }

            if !rtio_crg::check() {
                try!(host_write(stream, host::Reply::ClockFailure));
                return Err(io_error("RTIO clock failure"))
            }
        }

        try!(waiter.relinquish())
    }
}

fn flash_kernel_worker(waiter: Waiter,
                       congress: &mut Congress,
                       config_key: &str) -> io::Result<()> {
    let mut session = Session::new(congress);

    let kernel = config::read_to_end(config_key);
    if kernel.len() == 0 {
        return Err(io::Error::new(io::ErrorKind::NotFound, "kernel not found"))
    }

    try!(unsafe { kern_load(waiter, &mut session, &kernel) });
    try!(kern_run(&mut session));

    loop {
        if mailbox::receive() != 0 {
            if try!(process_kern_message(waiter, None, &mut session)) {
                return Ok(())
            }
        }

        if session.watchdog_set.expired() {
            return Err(io_error("watchdog expired"))
        }

        if !rtio_crg::check() {
            return Err(io_error("RTIO clock failure"))
        }

        try!(waiter.relinquish())
    }
}

fn respawn<F>(spawner: Spawner, waiter: Waiter,
              handle: &mut Option<ThreadHandle>,
              f: F) where F: 'static + FnOnce(Waiter, Spawner) + Send {
    match handle.take() {
        None => (),
        Some(handle) => {
            if !handle.terminated() {
                info!("terminating running kernel");
                handle.interrupt();
                waiter.join(handle).expect("cannot join interrupt thread")
            }
        }
    }

    *handle = Some(spawner.spawn(16384, f))
}

pub fn thread(waiter: Waiter, spawner: Spawner) {
    let congress = Urc::new(RefCell::new(Congress::new()));

    info!("running startup kernel");
    match flash_kernel_worker(waiter, &mut congress.borrow_mut(), "startup_kernel") {
        Ok(()) => info!("startup kernel finished"),
        Err(err) => {
            if err.kind() == io::ErrorKind::NotFound {
                info!("no startup kernel found")
            } else {
                error!("startup kernel aborted: {}", err);
            }
        }
    }

    let addr = SocketAddr::new(IP_ANY, 1381);
    let listener = TcpListener::bind(waiter, addr).expect("cannot bind socket");
    listener.set_keepalive(true);
    info!("accepting network sessions in Rust");

    let mut kernel_thread = None;
    loop {
        if listener.acceptable() {
            let (mut stream, addr) = listener.accept().expect("cannot accept client");
            match check_magic(&mut stream) {
                Ok(()) => (),
                Err(_) => continue
            }
            info!("new connection from {}", addr);

            let stream = stream.into_lower();
            let congress = congress.clone();
            respawn(spawner.clone(), waiter, &mut kernel_thread, move |waiter, _spawner| {
                let mut stream = TcpStream::from_lower(waiter, stream);
                let mut congress = congress.borrow_mut();
                match host_kernel_worker(waiter, &mut stream, &mut congress) {
                    Ok(()) => (),
                    Err(err) => {
                        if err.kind() == io::ErrorKind::UnexpectedEof {
                            info!("connection closed");
                        } else {
                            error!("session aborted: {}", err);
                        }
                    }
                }
            })
        }

        if kernel_thread.as_ref().map_or(true, |h| h.terminated()) {
            info!("no connection, starting idle kernel");

            let congress = congress.clone();
            respawn(spawner.clone(), waiter, &mut kernel_thread, move |waiter, _spawner| {
                let mut congress = congress.borrow_mut();
                match flash_kernel_worker(waiter, &mut congress, "idle_kernel") {
                    Ok(()) =>
                        info!("idle kernel finished, standing by"),
                    Err(err) => {
                        if err.kind() == io::ErrorKind::Interrupted {
                            info!("idle kernel interrupted");
                        } else if err.kind() == io::ErrorKind::NotFound {
                            info!("no idle kernel found");
                            while waiter.relinquish().is_ok() {}
                        } else {
                            error!("idle kernel aborted: {}", err);
                        }
                    }
                }
            })
        }

        let _ = waiter.relinquish();
    }
}
