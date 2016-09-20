extern crate fringe;
extern crate lwip;

use std::cell::RefCell;
use std::vec::Vec;
use std::time::{Instant, Duration};
use std::io::{Read, Write, Result, Error, ErrorKind};
use self::fringe::OwnedStack;
use self::fringe::generator::{Generator, Yielder};

#[derive(Debug)]
struct WaitRequest {
    timeout: Option<Instant>,
    event:   Option<WaitEvent>
}

#[derive(Debug)]
enum WaitResult {
    Completed,
    TimedOut,
    Interrupted
}

#[derive(Debug)]
struct Thread {
    generator:   Generator<WaitResult, WaitRequest, OwnedStack>,
    waiting_for: WaitRequest,
    interrupted: bool
}

#[derive(Debug)]
pub struct Scheduler {
    threads: Vec<Thread>,
    index:   usize
}

impl Scheduler {
    pub fn new() -> Scheduler {
        Scheduler { threads: Vec::new(), index: 0 }
    }

    pub unsafe fn spawn<F: FnOnce(Waiter) + Send + 'static>(&mut self, stack_size: usize, f: F) {
        let stack = OwnedStack::new(stack_size);
        let thread = Thread {
            generator:   Generator::unsafe_new(stack, move |yielder, _| {
                f(Waiter(yielder))
            }),
            waiting_for: WaitRequest {
                timeout: None,
                event:   None
            },
            interrupted: false
        };
        self.threads.push(thread)
    }

    pub fn run(&mut self) {
        if self.threads.len() == 0 { return }

        let now = Instant::now();

        let start_index = self.index;
        loop {
            self.index = (self.index + 1) % self.threads.len();

            let result = {
                let thread = &mut self.threads[self.index];
                match thread.waiting_for {
                    _ if thread.interrupted => {
                        thread.interrupted = false;
                        thread.generator.resume(WaitResult::Interrupted)
                    }
                    WaitRequest { timeout: Some(instant), .. } if now >= instant =>
                        thread.generator.resume(WaitResult::TimedOut),
                    WaitRequest { event: Some(ref event), .. } if event.completed() =>
                        thread.generator.resume(WaitResult::Completed),
                    WaitRequest { timeout: None, event: None } =>
                        thread.generator.resume(WaitResult::Completed),
                    _ => {
                        if self.index == start_index {
                            // We've checked every thread and none of them are runnable.
                            break
                        } else {
                            continue
                        }
                    }
                }
            };

            match result {
                None => {
                    // The thread has terminated.
                    self.threads.remove(self.index);
                    self.index = 0
                },
                Some(wait_request) => {
                    // The thread has suspended itself.
                    self.threads[self.index].waiting_for = wait_request
                }
            }

            break
        }
    }
}

#[derive(Debug)]
enum WaitEvent {
    UdpReadable(*const RefCell<lwip::UdpSocketState>),
    TcpAcceptable(*const RefCell<lwip::TcpListenerState>),
    TcpWriteable(*const RefCell<lwip::TcpStreamState>),
    TcpReadable(*const RefCell<lwip::TcpStreamState>),
}

impl WaitEvent {
    fn completed(&self) -> bool {
        match *self {
            WaitEvent::UdpReadable(state) =>
                unsafe { (*state).borrow().readable() },
            WaitEvent::TcpAcceptable(state) =>
                unsafe { (*state).borrow().acceptable() },
            WaitEvent::TcpWriteable(state) =>
                unsafe { (*state).borrow().writeable() },
            WaitEvent::TcpReadable(state) =>
                unsafe { (*state).borrow().readable() },
        }
    }
}

unsafe impl Send for WaitEvent {}

#[derive(Debug, Clone, Copy)]
pub struct Waiter<'a>(&'a Yielder<WaitResult, WaitRequest, OwnedStack>);

impl<'a> Waiter<'a> {
    pub fn sleep(&self, duration: Duration) -> Result<()> {
        let request = WaitRequest {
            timeout: Some(Instant::now() + duration),
            event:   None
        };

        match self.0.suspend(request) {
            WaitResult::TimedOut => Ok(()),
            WaitResult::Interrupted => Err(Error::new(ErrorKind::Interrupted, "")),
            _ => unreachable!()
        }
    }

    fn suspend(&self, request: WaitRequest) -> Result<()> {
        match self.0.suspend(request) {
            WaitResult::Completed => Ok(()),
            WaitResult::TimedOut => Err(Error::new(ErrorKind::TimedOut, "")),
            WaitResult::Interrupted => Err(Error::new(ErrorKind::Interrupted, ""))
        }
    }

    pub fn udp_readable(&self, socket: &lwip::UdpSocket) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::UdpReadable(socket.state()))
        })
    }

    pub fn tcp_acceptable(&self, socket: &lwip::TcpListener) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::TcpAcceptable(socket.state()))
        })
    }

    pub fn tcp_writeable(&self, socket: &lwip::TcpStream) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::TcpWriteable(socket.state()))
        })
    }

    pub fn tcp_readable(&self, socket: &lwip::TcpStream) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::TcpReadable(socket.state()))
        })
    }
}

// Wrappers around lwip

pub use self::lwip::{IpAddr, IP4_ANY, IP6_ANY, IP_ANY, SocketAddr};

#[derive(Debug)]
pub struct UdpSocket<'a> {
    waiter: Waiter<'a>,
    lower:  lwip::UdpSocket
}

impl<'a> UdpSocket<'a> {
    pub fn new(waiter: Waiter<'a>) -> Result<UdpSocket> {
        Ok(UdpSocket {
            waiter: waiter,
            lower:  try!(lwip::UdpSocket::new())
        })
    }

    pub fn bind(&self, addr: SocketAddr) -> Result<()> {
        Ok(try!(self.lower.bind(addr)))
    }

    pub fn connect(&self, addr: SocketAddr) -> Result<()> {
        Ok(try!(self.lower.connect(addr)))
    }

    pub fn disconnect(&self) -> Result<()> {
        Ok(try!(self.lower.disconnect()))
    }

    pub fn send_to(&self, buf: &[u8], addr: SocketAddr) -> Result<usize> {
        try!(self.lower.send_to(lwip::Pbuf::from_slice(buf), addr));
        Ok(buf.len())
    }

    pub fn recv_from(&self, buf: &mut [u8]) -> Result<(usize, SocketAddr)> {
        try!(self.waiter.udp_readable(&self.lower));
        let (pbuf, addr) = self.lower.try_recv().unwrap();
        let len = ::std::cmp::min(buf.len(), pbuf.len());
        (&mut buf[..len]).copy_from_slice(&pbuf.as_slice()[..len]);
        Ok((len, addr))
    }

    pub fn send(&self, buf: &[u8]) -> Result<usize> {
        try!(self.lower.send(lwip::Pbuf::from_slice(buf)));
        Ok(buf.len())
    }

    pub fn recv(&self, buf: &mut [u8]) -> Result<usize> {
        try!(self.waiter.udp_readable(&self.lower));
        let (pbuf, _addr) = self.lower.try_recv().unwrap();
        // lwip checks that addr matches the bind/connect call
        let len = ::std::cmp::min(buf.len(), pbuf.len());
        (&mut buf[..len]).copy_from_slice(&pbuf.as_slice()[..len]);
        Ok(len)
    }
}

#[derive(Debug)]
pub struct TcpListener<'a> {
    waiter: Waiter<'a>,
    lower:  lwip::TcpListener
}

impl<'a> TcpListener<'a> {
    pub fn bind(waiter: Waiter<'a>, addr: SocketAddr) -> Result<TcpListener> {
        Ok(TcpListener {
            waiter: waiter,
            lower:  try!(lwip::TcpListener::bind(addr))
        })
    }

    pub fn accept(&self) -> Result<(TcpStream, SocketAddr)> {
        try!(self.waiter.tcp_acceptable(&self.lower));
        loop {}
        let stream_lower = self.lower.try_accept().unwrap();
        let addr = SocketAddr::new(IP_ANY, 0); // FIXME: coax lwip into giving real addr here
        Ok((TcpStream {
            waiter: self.waiter,
            lower:  stream_lower,
            buffer: None
        }, addr))
    }
}

pub use self::lwip::Shutdown;

#[derive(Debug)]
pub struct TcpStream<'a> {
    waiter: Waiter<'a>,
    lower:  lwip::TcpStream,
    buffer: Option<(lwip::Pbuf<'static>, usize)>
}

impl<'a> TcpStream<'a> {
    pub fn shutdown(&self, how: Shutdown) -> Result<()> {
        Ok(try!(self.lower.shutdown(how)))
    }
}

impl<'a> Read for TcpStream<'a> {
    fn read(&mut self, buf: &mut [u8]) -> Result<usize> {
        if self.buffer.is_none() {
            try!(self.waiter.tcp_readable(&self.lower));
            let pbuf = try!(self.lower.try_read()).unwrap();
            self.buffer = Some((pbuf, 0))
        }

        let (pbuf, pos) = self.buffer.take().unwrap();
        let slice = &pbuf.as_slice()[pos..];
        let len = ::std::cmp::min(buf.len(), slice.len());
        buf.copy_from_slice(&slice[..len]);
        if len < slice.len() {
            self.buffer = Some((pbuf, pos + len))
        }
        Ok(len)
    }
}

impl<'a> Write for TcpStream<'a> {
    fn write(&mut self, buf: &[u8]) -> Result<usize> {
        try!(self.waiter.tcp_writeable(&self.lower));
        Ok(try!(self.lower.write(buf)))
    }

    fn flush(&mut self) -> Result<()> {
        Ok(try!(self.lower.flush()))
    }
}
