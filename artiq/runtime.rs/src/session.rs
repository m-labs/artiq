use std::prelude::v1::*;
use std::str;
use std::io::{self, Read, ErrorKind};
use {config, rtio_crg};
use logger::BufferLogger;
use sched::{Waiter, TcpListener, TcpStream, SocketAddr, IP_ANY};
use session_proto::*;

#[derive(Debug, Clone, Copy)]
enum KernelState {
    Absent,
    Loaded,
    Running,
    RpcWait
}

#[derive(Debug)]
pub struct Session {
    kernel_state: KernelState,
}

extern {
    fn kloader_stop();
    fn watchdog_init();
    fn kloader_start_idle_kernel();
}

impl Session {
    pub fn new() -> Session {
        unsafe { kloader_stop(); }
        Session {
            kernel_state: KernelState::Absent
        }
    }

    pub fn running(&self) -> bool {
        match self.kernel_state {
            KernelState::Absent  | KernelState::Loaded  => false,
            KernelState::Running | KernelState::RpcWait => true
        }
    }
}

impl Drop for Session {
    fn drop(&mut self) {
        unsafe {
            kloader_stop();
            watchdog_init();
            kloader_start_idle_kernel();
        }
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

fn handle_request(stream: &mut TcpStream,
                  logger: &BufferLogger,
                  session: &mut Session) -> io::Result<()> {
    fn read_request(stream: &mut TcpStream) -> io::Result<Request> {
        let request = try!(Request::read_from(stream));
        match &request {
            &Request::LoadLibrary(_) => trace!("comm<-host LoadLibrary(...)"),
            _ => trace!("comm<-host {:?}", request)
        }
        Ok(request)
    }

    fn write_reply(stream: &mut TcpStream, reply: Reply) -> io::Result<()> {
        trace!("comm->host {:?}", reply);
        reply.write_to(stream)
    }

    match try!(read_request(stream)) {
        Request::Ident =>
            write_reply(stream, Reply::Ident(::board::ident(&mut [0; 64]))),

        // artiq_corelog
        Request::Log => {
            // Logging the packet with the log is inadvisable
            trace!("comm->host Log(...)");
            logger.extract(move |log| {
                Reply::Log(log).write_to(stream)
            })
        }

        Request::LogClear => {
            logger.clear();
            write_reply(stream, Reply::Log(""))
        }

        // artiq_coreconfig
        Request::FlashRead { ref key } => {
            let value = config::read_to_end(key);
            write_reply(stream, Reply::FlashRead(&value))
        }

        Request::FlashWrite { ref key, ref value } => {
            match config::write(key, value) {
                Ok(_)  => write_reply(stream, Reply::FlashOk),
                Err(_) => write_reply(stream, Reply::FlashError)
            }
        }

        Request::FlashRemove { ref key } => {
            config::remove(key);
            write_reply(stream, Reply::FlashOk)
        }

        Request::FlashErase => {
            config::erase();
            write_reply(stream, Reply::FlashOk)
        }

        // artiq_run/artiq_master
        Request::SwitchClock(clk) => {
            if session.running() {
                error!("attempted to switch RTIO clock while kernel was running");
                write_reply(stream, Reply::ClockSwitchFailed)
            } else {
                if rtio_crg::switch_clock(clk) {
                    write_reply(stream, Reply::ClockSwitchCompleted)
                } else {
                    write_reply(stream, Reply::ClockSwitchFailed)
                }
            }
        }

        _ => unreachable!()
    }
}

fn handle_requests(stream: &mut TcpStream,
                   logger: &BufferLogger) -> io::Result<()> {
    try!(check_magic(stream));

    let mut session = Session::new();
    loop {
        try!(handle_request(stream, logger, &mut session))
    }
}

pub fn handler(waiter: Waiter,
               logger: &BufferLogger) {
    let addr = SocketAddr::new(IP_ANY, 1381);
    let listener = TcpListener::bind(waiter, addr).unwrap();
    info!("accepting network sessions in Rust");

    loop {
        let (mut stream, addr) = listener.accept().unwrap();
        info!("new connection from {:?}", addr);

        match handle_requests(&mut stream, logger) {
            Ok(()) => (),
            Err(err) => {
                if err.kind() == ErrorKind::UnexpectedEof {
                    info!("connection closed");
                } else {
                    error!("cannot handle network request: {:?}", err);
                }
            }
        }
    }
}
