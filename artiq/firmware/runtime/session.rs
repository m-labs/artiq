use std::prelude::v1::*;
use std::{mem, str};
use std::cell::RefCell;
use std::io::{self, Read, Write};
use std::btree_set::BTreeSet;
use {config, rtio_mgt, mailbox, rpc_queue, kernel};
use logger::BufferLogger;
use cache::Cache;
use urc::Urc;
use sched::{ThreadHandle, Io};
use sched::{TcpSocket};
use byteorder::{ByteOrder, NetworkEndian};
use board;

use rpc_proto as rpc;
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
    watchdog_set: board::clock::WatchdogSet,
    log_buffer: String,
    interner: BTreeSet<String>
}

impl<'a> Session<'a> {
    fn new(congress: &mut Congress) -> Session {
        Session {
            congress: congress,
            kernel_state: KernelState::Absent,
            watchdog_set: board::clock::WatchdogSet::new(),
            log_buffer: String::new(),
            interner: BTreeSet::new()
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

fn check_magic(stream: &mut TcpSocket) -> io::Result<()> {
    const MAGIC: &'static [u8] = b"ARTIQ coredev\n";

    let mut magic: [u8; 14] = [0; 14];
    try!(stream.read_exact(&mut magic));
    if magic != MAGIC {
        Err(io::Error::new(io::ErrorKind::InvalidData, "unrecognized magic"))
    } else {
        Ok(())
    }
}

fn host_read(stream: &mut TcpSocket) -> io::Result<host::Request> {
    let request = try!(host::Request::read_from(stream));
    match &request {
        &host::Request::LoadKernel(_) => trace!("comm<-host LoadLibrary(...)"),
        _ => trace!("comm<-host {:?}", request)
    }
    Ok(request)
}

fn host_write(stream: &mut Write, reply: host::Reply) -> io::Result<()> {
    trace!("comm->host {:?}", reply);
    reply.write_to(stream)
}

fn kern_send(io: &Io, request: &kern::Message) -> io::Result<()> {
    match request {
        &kern::LoadRequest(_) => trace!("comm->kern LoadRequest(...)"),
        _ => trace!("comm->kern {:?}", request)
    }
    unsafe { mailbox::send(request as *const _ as usize) }
    io.until(mailbox::acknowledged)
}

fn kern_recv_notrace<R, F>(io: &Io, f: F) -> io::Result<R>
        where F: FnOnce(&kern::Message) -> io::Result<R> {
    try!(io.until(|| mailbox::receive() != 0));
    if !kernel::validate(mailbox::receive()) {
        let message = format!("invalid kernel CPU pointer 0x{:x}", mailbox::receive());
        return Err(io::Error::new(io::ErrorKind::InvalidData, message))
    }

    f(unsafe { mem::transmute::<usize, &kern::Message>(mailbox::receive()) })
}

fn kern_recv_dotrace(reply: &kern::Message) {
    match reply {
        &kern::Log(_) => trace!("comm<-kern Log(...)"),
        &kern::LogSlice(_) => trace!("comm<-kern LogSlice(...)"),
        _ => trace!("comm<-kern {:?}", reply)
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

fn kern_acknowledge() -> io::Result<()> {
    mailbox::acknowledge();
    Ok(())
}

unsafe fn kern_load(io: &Io, session: &mut Session, library: &[u8]) -> io::Result<()> {
    if session.running() {
        unexpected!("attempted to load a new kernel while a kernel was running")
    }

    kernel::start();

    try!(kern_send(io, &kern::LoadRequest(&library)));
    kern_recv(io, |reply| {
        match reply {
            &kern::LoadReply(Ok(())) => {
                session.kernel_state = KernelState::Loaded;
                Ok(())
            }
            &kern::LoadReply(Err(error)) =>
                unexpected!("cannot load kernel: {}", error),
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
                        stream: &mut TcpSocket,
                        session: &mut Session) -> io::Result<()> {
    match try!(host_read(stream)) {
        host::Request::Ident =>
            host_write(stream, host::Reply::Ident(board::ident(&mut [0; 64]))),

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

            if rtio_mgt::crg::switch_clock(clk) {
                host_write(stream, host::Reply::ClockSwitchCompleted)
            } else {
                host_write(stream, host::Reply::ClockSwitchFailed)
            }
        }

        host::Request::LoadKernel(kernel) =>
            match unsafe { kern_load(io, session, &kernel) } {
                Ok(()) => host_write(stream, host::Reply::LoadCompleted),
                Err(_) => {
                    try!(kern_acknowledge());
                    host_write(stream, host::Reply::LoadFailed)
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

            let slot = try!(kern_recv(io, |reply| {
                match reply {
                    &kern::RpcRecvRequest(slot) => Ok(slot),
                    other => unexpected!("unexpected reply from kernel CPU: {:?}", other)
                }
            }));
            try!(rpc::recv_return(stream, &tag, slot, &|size| {
                try!(kern_send(io, &kern::RpcRecvReply(Ok(size))));
                kern_recv(io, |reply| {
                    match reply {
                        &kern::RpcRecvRequest(slot) => Ok(slot),
                        other => unexpected!("unexpected reply from kernel CPU: {:?}", other)
                    }
                })
            }));
            try!(kern_send(io, &kern::RpcRecvReply(Ok(0))));

            session.kernel_state = KernelState::Running;
            Ok(())
        }

        host::Request::RpcException {
            name, message, param, file, line, column, function
        } => {
            if session.kernel_state != KernelState::RpcWait {
                unexpected!("unsolicited RPC reply")
            }

            try!(kern_recv(io, |reply| {
                match reply {
                    &kern::RpcRecvRequest(_) => Ok(()),
                    other =>
                        unexpected!("unexpected reply from kernel CPU: {:?}", other)
                }
            }));

            // FIXME: gross.
            fn into_c_str(interner: &mut BTreeSet<String>, s: String) -> *const u8 {
                let s = s + "\0";
                interner.insert(s.clone());
                let p = interner.get(&s).unwrap().as_bytes().as_ptr();
                p
            }
            let exn = kern::Exception {
                name: into_c_str(&mut session.interner, name),
                message: into_c_str(&mut session.interner, message),
                param: param,
                file: into_c_str(&mut session.interner, file),
                line: line,
                column: column,
                function: into_c_str(&mut session.interner, function),
                phantom: ::core::marker::PhantomData
            };
            try!(kern_send(io, &kern::RpcRecvReply(Err(exn))));

            session.kernel_state = KernelState::Running;
            Ok(())
        }
    }
}

fn process_kern_message(io: &Io,
                        mut stream: Option<&mut TcpSocket>,
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
        match request {
            &kern::Log(args) => {
                use std::fmt::Write;
                try!(session.log_buffer.write_fmt(args)
                        .map_err(|_| io_error("cannot append to session log buffer")));
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

            &kern::RTIOInitRequest => {
                info!("resetting RTIO");
                rtio_mgt::init_core();
                kern_acknowledge()
            }

            &kern::DRTIOChannelStateRequest { channel } => {
                let (fifo_space, last_timestamp) = rtio_mgt::drtio_dbg::get_channel_state(channel);
                kern_send(io, &kern::DRTIOChannelStateReply { fifo_space: fifo_space,
                                                                  last_timestamp: last_timestamp })
            }
            &kern::DRTIOResetChannelStateRequest { channel } => {
                rtio_mgt::drtio_dbg::reset_channel_state(channel);
                kern_acknowledge()
            }
            &kern::DRTIOGetFIFOSpaceRequest { channel } => {
                rtio_mgt::drtio_dbg::get_fifo_space(channel);
                kern_acknowledge()
            }
            &kern::DRTIOPacketCountRequest => {
                let (tx_cnt, rx_cnt) = rtio_mgt::drtio_dbg::get_packet_counts();
                kern_send(io, &kern::DRTIOPacketCountReply { tx_cnt: tx_cnt, rx_cnt: rx_cnt })
            }
            &kern::DRTIOFIFOSpaceReqCountRequest => {
                let cnt = rtio_mgt::drtio_dbg::get_fifo_space_req_count();
                kern_send(io, &kern::DRTIOFIFOSpaceReqCountReply { cnt: cnt })
            }

            &kern::WatchdogSetRequest { ms } => {
                let id = try!(session.watchdog_set.set_ms(ms)
                                .map_err(|()| io_error("out of watchdogs")));
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
                        try!(host_write(stream, host::Reply::RpcRequest { async: async }));
                        try!(rpc::send_args(stream, service, tag, data));
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

            #[cfg(has_i2c)]
            &kern::I2CStartRequest { busno } => {
                board::i2c::start(busno);
                kern_acknowledge()
            }
            #[cfg(has_i2c)]
            &kern::I2CStopRequest { busno } => {
                board::i2c::stop(busno);
                kern_acknowledge()
            }
            #[cfg(has_i2c)]
            &kern::I2CWriteRequest { busno, data } => {
                let ack = board::i2c::write(busno, data);
                kern_send(io, &kern::I2CWriteReply { ack: ack })
            }
            #[cfg(has_i2c)]
            &kern::I2CReadRequest { busno, ack } => {
                let data = board::i2c::read(busno, ack);
                kern_send(io, &kern::I2CReadReply { data: data })
            }

            #[cfg(not(has_i2c))]
            &kern::I2CStartRequest { .. } => {
                kern_acknowledge()
            }
            #[cfg(not(has_i2c))]
            &kern::I2CStopRequest { .. } => {
                kern_acknowledge()
            }
            #[cfg(not(has_i2c))]
            &kern::I2CWriteRequest { .. } => {
                kern_send(io, &kern::I2CWriteReply { ack: false })
            }
            #[cfg(not(has_i2c))]
            &kern::I2CReadRequest { .. } => {
                kern_send(io, &kern::I2CReadReply { data: 0xff })
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

            &kern::RunException { exception: ref exn, backtrace } => {
                unsafe { kernel::stop() }
                session.kernel_state = KernelState::Absent;
                unsafe { session.congress.cache.unborrow() }

                unsafe fn from_c_str<'a>(s: *const u8) -> &'a str {
                    use ::libc::{c_char, size_t};
                    use core::slice;
                    extern { fn strlen(s: *const c_char) -> size_t; }
                    let s = slice::from_raw_parts(s, strlen(s as *const c_char));
                    str::from_utf8_unchecked(s)
                }
                let name = unsafe { from_c_str(exn.name) };
                let message = unsafe { from_c_str(exn.message) };
                let file = unsafe { from_c_str(exn.file) };
                let function = unsafe { from_c_str(exn.function) };
                match stream {
                    None => {
                        error!("exception in flash kernel");
                        error!("{}: {} {:?}", name, message, exn.param);
                        error!("at {}:{}:{} in {}", file, exn.line, exn.column, function);
                        return Ok(true)
                    },
                    Some(ref mut stream) =>
                        host_write(stream, host::Reply::KernelException {
                            name: name,
                            message: message,
                            param: exn.param,
                            file: file,
                            line: exn.line,
                            column: exn.column,
                            function: function,
                            backtrace: backtrace
                        })
                }
            }

            request => unexpected!("unexpected request {:?} from kernel CPU", request)
        }.and(Ok(false))
    })
}

fn process_kern_queued_rpc(stream: &mut TcpSocket,
                           _session: &mut Session) -> io::Result<()> {
    rpc_queue::dequeue(|slice| {
        trace!("comm<-kern (async RPC)");
        let length = NetworkEndian::read_u32(slice) as usize;
        try!(host_write(stream, host::Reply::RpcRequest { async: true }));
        trace!("{:?}" ,&slice[4..][..length]);
        try!(stream.write(&slice[4..][..length]));
        Ok(())
    })
}

fn host_kernel_worker(io: &Io,
                      stream: &mut TcpSocket,
                      congress: &mut Congress) -> io::Result<()> {
    let mut session = Session::new(congress);

    loop {
        while !rpc_queue::empty() {
            try!(process_kern_queued_rpc(stream, &mut session))
        }

        if stream.can_recv() {
            try!(process_host_message(io, stream, &mut session))
        } else if !stream.may_recv() {
            return Ok(())
        }

        if mailbox::receive() != 0 {
            try!(process_kern_message(io, Some(stream), &mut session));
        }

        if session.kernel_state == KernelState::Running {
            if session.watchdog_set.expired() {
                try!(host_write(stream, host::Reply::WatchdogExpired));
                return Err(io_error("watchdog expired"))
            }

            if !rtio_mgt::crg::check() {
                try!(host_write(stream, host::Reply::ClockFailure));
                return Err(io_error("RTIO clock failure"))
            }
        }

        try!(io.relinquish())
    }
}

fn flash_kernel_worker(io: &Io,
                       congress: &mut Congress,
                       config_key: &str) -> io::Result<()> {
    let mut session = Session::new(congress);

    let kernel = config::read_to_end(config_key);
    if kernel.len() == 0 {
        return Err(io::Error::new(io::ErrorKind::NotFound, "kernel not found"))
    }

    try!(unsafe { kern_load(io, &mut session, &kernel) });
    try!(kern_run(&mut session));

    loop {
        if !rpc_queue::empty() {
            return Err(io_error("unexpected background RPC in flash kernel"))
        }

        if mailbox::receive() != 0 {
            if try!(process_kern_message(io, None, &mut session)) {
                return Ok(())
            }
        }

        if session.watchdog_set.expired() {
            return Err(io_error("watchdog expired"))
        }

        if !rtio_mgt::crg::check() {
            return Err(io_error("RTIO clock failure"))
        }

        try!(io.relinquish())
    }
}

fn respawn<F>(io: &Io, handle: &mut Option<ThreadHandle>, f: F)
        where F: 'static + FnOnce(Io) + Send {
    match handle.take() {
        None => (),
        Some(handle) => {
            if !handle.terminated() {
                info!("terminating running kernel");
                handle.interrupt();
                io.join(handle).expect("cannot join interrupt thread")
            }
        }
    }

    *handle = Some(io.spawn(16384, f))
}

pub fn thread(io: Io) {
    let congress = Urc::new(RefCell::new(Congress::new()));

    info!("running startup kernel");
    match flash_kernel_worker(&io, &mut *borrow_mut!(congress), "startup_kernel") {
        Ok(()) => info!("startup kernel finished"),
        Err(err) => {
            if err.kind() == io::ErrorKind::NotFound {
                info!("no startup kernel found")
            } else {
                error!("startup kernel aborted: {}", err);
            }
        }
    }

    BufferLogger::with_instance(|logger| logger.disable_trace_to_uart());

    const BUFFER_SIZE: usize = 65535;
    let mut listener = TcpSocket::with_buffer_size(&io, BUFFER_SIZE);
    info!("accepting network sessions");

    let mut kernel_thread = None;
    loop {
        if !listener.is_open() {
            listener.listen(1381).expect("session: cannot listen")
        }

        if listener.is_active() {
            listener.accept().expect("session: cannot accept");
            match check_magic(&mut listener) {
                Ok(()) => (),
                Err(_) => {
                    warn!("wrong magic from {}", listener.remote_endpoint());
                    listener.close().expect("session: cannot close");
                    continue
                }
            }
            info!("new connection from {}", listener.remote_endpoint());

            let socket = listener.into_handle();
            listener = TcpSocket::with_buffer_size(&io, BUFFER_SIZE);

            let congress = congress.clone();
            respawn(&io, &mut kernel_thread, move |io| {
                let mut congress = borrow_mut!(congress);
                let mut socket = TcpSocket::from_handle(&io, socket);
                match host_kernel_worker(&io, &mut socket, &mut *congress) {
                    Ok(()) => (),
                    Err(err) => {
                        if err.kind() == io::ErrorKind::UnexpectedEof {
                            info!("connection closed");
                        } else {
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
