use std::prelude::v1::*;
use std::str;
use std::io::{self, Read, ErrorKind};
use self::protocol::*;

mod protocol;

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
    pub fn start() -> Session {
        unsafe { kloader_stop(); }
        Session {
            kernel_state: KernelState::Absent
        }
    }

    pub fn end(self) {
        unsafe {
            kloader_stop();
            watchdog_init();
            kloader_start_idle_kernel();
        }
    }
}

fn check_magic(stream: &mut ::io::TcpStream) -> io::Result<()> {
    const MAGIC: &'static [u8] = b"ARTIQ coredev\n";

    let mut magic: [u8; 14] = [0; 14];
    try!(stream.read_exact(&mut magic));
    if magic != MAGIC {
        Err(io::Error::new(io::ErrorKind::InvalidData, "unrecognized magic"))
    } else {
        Ok(())
    }
}

fn handle_request(stream: &mut ::io::TcpStream,
                  logger: &::buffer_logger::BufferLogger) -> io::Result<()> {
    fn read_request(stream: &mut ::io::TcpStream) -> io::Result<Request> {
        let request = try!(Request::read_from(stream));
        trace!("comm<-host {:?}", request);
        Ok(request)
    }

    fn write_reply(stream: &mut ::io::TcpStream, reply: Reply) -> io::Result<()> {
        trace!("comm->host {:?}", reply);
        reply.write_to(stream)
    }

    match try!(read_request(stream)) {
        Request::Ident => {
            write_reply(stream, Reply::Ident(::board::ident(&mut [0; 64])))
        }

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

        _ => unreachable!()
    }
}

fn handle_requests(stream: &mut ::io::TcpStream,
                   logger: &::buffer_logger::BufferLogger) -> io::Result<()> {
    try!(check_magic(stream));
    loop {
        try!(handle_request(stream, logger))
    }
}

pub fn handler(waiter: ::io::Waiter,
               logger: &::buffer_logger::BufferLogger) {
    let addr = ::io::SocketAddr::new(::io::IP_ANY, 1381);
    let listener = ::io::TcpListener::bind(waiter, addr).unwrap();
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
