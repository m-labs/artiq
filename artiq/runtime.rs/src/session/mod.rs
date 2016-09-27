use std::prelude::v1::*;
use std::io::{self, Read};
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

fn handle_request(stream: &mut ::io::TcpStream) -> io::Result<()> {
    fn read_request(stream: &mut ::io::TcpStream) -> io::Result<Request> {
        let request = try!(Request::read_from(stream));
        println!("comm<-host {:?}", request);
        Ok(request)
    }

    fn write_reply(stream: &mut ::io::TcpStream, reply: Reply) -> io::Result<()> {
        println!("comm->host {:?}", reply);
        reply.write_to(stream)
    }

    match try!(read_request(stream)) {
        Request::Ident => {
            let mut ident: [u8; 256];
            let ident = unsafe {
                extern { fn get_ident(ident: *mut u8); }

                ident = ::core::mem::uninitialized();
                get_ident(ident.as_mut_ptr());
                &ident[..ident.iter().position(|&c| c == 0).unwrap()]
            };

            write_reply(stream, Reply::Ident(ident))
        },
        _ => unreachable!()
    }
}

fn handle_requests(stream: &mut ::io::TcpStream) -> io::Result<()> {
    try!(check_magic(stream));
    loop {
        try!(handle_request(stream))
    }
}

pub fn handler(waiter: ::io::Waiter) {
    let addr = ::io::SocketAddr::new(::io::IP_ANY, 1381);
    let listener = ::io::TcpListener::bind(waiter, addr).unwrap();
    loop {
        let (mut stream, _addr) = listener.accept().unwrap();
        match handle_requests(&mut stream) {
            Ok(()) => (),
            Err(err) => {
                println!("cannot handle network request: {:?}", err);
            }
        }
    }
}
