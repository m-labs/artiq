#![allow(dead_code)]

use std::cell::RefCell;
use std::vec::Vec;
use std::time::{Instant, Duration};
use std::io::{Read, Write, Result, Error, ErrorKind};
use fringe::OwnedStack;
use fringe::generator::{Generator, Yielder, State as GeneratorState};
use lwip;
use urc::Urc;

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
    generator: Generator<WaitResult, WaitRequest, OwnedStack>,
    waiting_for: WaitRequest,
    interrupted: bool
}

impl Thread {
    unsafe fn new<F>(spawner: Spawner, stack_size: usize, f: F) -> ThreadHandle
            where F: 'static + FnOnce(Waiter, Spawner) + Send {
        let stack = OwnedStack::new(stack_size);
        ThreadHandle::new(Thread {
            generator: Generator::unsafe_new(stack, |yielder, _| {
                f(Waiter(yielder), spawner)
            }),
            waiting_for: WaitRequest {
                timeout: None,
                event:   None
            },
            interrupted: false
        })
    }

    pub fn terminated(&self) -> bool {
        // FIXME: https://github.com/nathan7/libfringe/pull/56
        match self.generator.state() {
            GeneratorState::Unavailable => true,
            GeneratorState::Runnable => false
        }
    }

    pub fn interrupt(&mut self) {
        self.interrupted = true
    }
}

#[derive(Debug, Clone)]
pub struct ThreadHandle(Urc<RefCell<Thread>>);

impl ThreadHandle {
    fn new(thread: Thread) -> ThreadHandle {
        ThreadHandle(Urc::new(RefCell::new(thread)))
    }

    pub fn terminated(&self) -> bool {
        match self.0.try_borrow() {
            Ok(thread) => thread.terminated(),
            Err(_) => false // the running thread hasn't terminated
        }
    }

    pub fn interrupt(&self) {
        match self.0.try_borrow_mut() {
            Ok(mut thread) => thread.interrupt(),
            Err(_) => panic!("cannot interrupt the running thread")
        }
    }
}

#[derive(Debug)]
pub struct Scheduler {
    threads: Vec<ThreadHandle>,
    index: usize,
    spawner: Spawner
}

impl Scheduler {
    pub fn new() -> Scheduler {
        Scheduler {
            threads: Vec::new(),
            index: 0,
            spawner: Spawner::new()
        }
    }

    pub fn spawner(&self) -> &Spawner {
        &self.spawner
    }

    pub fn run(&mut self) {
        self.threads.append(&mut *self.spawner.queue.borrow_mut());

        if self.threads.len() == 0 { return }

        let now = Instant::now();

        let start_index = self.index;
        loop {
            self.index = (self.index + 1) % self.threads.len();

            let result = {
                let thread = &mut *self.threads[self.index].0.borrow_mut();
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
                    let thread = &mut *self.threads[self.index].0.borrow_mut();
                    thread.waiting_for = wait_request
                }
            }

            break
        }
    }
}

#[derive(Debug, Clone)]
pub struct Spawner {
    queue: Urc<RefCell<Vec<ThreadHandle>>>
}

impl Spawner {
    fn new() -> Spawner {
        Spawner { queue: Urc::new(RefCell::new(Vec::new())) }
    }

    pub fn spawn<F>(&self, stack_size: usize, f: F) -> ThreadHandle
            where F: 'static + FnOnce(Waiter, Spawner) + Send {
        let handle = unsafe { Thread::new(self.clone(), stack_size, f) };
        self.queue.borrow_mut().push(handle.clone());
        handle
    }
}

enum WaitEvent {
    Completion(*const (Fn() -> bool + 'static)),
    Termination(*const RefCell<Thread>),
    UdpReadable(*const RefCell<lwip::UdpSocketState>),
    TcpAcceptable(*const RefCell<lwip::TcpListenerState>),
    TcpWriteable(*const RefCell<lwip::TcpStreamState>),
    TcpReadable(*const RefCell<lwip::TcpStreamState>),
}

impl WaitEvent {
    fn completed(&self) -> bool {
        match *self {
            WaitEvent::Completion(f) =>
                unsafe { (*f)() },
            WaitEvent::Termination(thread) =>
                unsafe { (*thread).borrow().terminated() },
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

// *const DST doesn't have impl Debug
impl ::core::fmt::Debug for WaitEvent {
    fn fmt(&self, f: &mut ::core::fmt::Formatter) ->
            ::core::result::Result<(), ::core::fmt::Error> {
        write!(f, "WaitEvent...")
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

    pub fn relinquish(&self) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   None
        })
    }

    pub fn join(&self, thread: ThreadHandle) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::Termination(&*thread.0))
        })
    }

    pub fn until<F: Fn() -> bool + 'static>(&self, f: F) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(WaitEvent::Completion(&f as *const _))
        })
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

pub use lwip::{IpAddr, IP4_ANY, IP6_ANY, IP_ANY, SocketAddr};

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

    pub fn into_lower(self) -> lwip::UdpSocket {
        self.lower
    }

    pub fn from_lower(waiter: Waiter<'a>, inner: lwip::UdpSocket) -> UdpSocket {
        UdpSocket { waiter: waiter, lower: inner }
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

    pub fn recv_from(&self, buf: &mut Vec<u8>) -> Result<SocketAddr> {
        try!(self.waiter.udp_readable(&self.lower));
        let (pbuf, addr) = self.lower.try_recv().unwrap();
        buf.clear();
        buf.extend_from_slice(&pbuf.as_slice());
        Ok(addr)
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

    pub fn readable(&self) -> bool {
        self.lower.state().borrow().readable()
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

    pub fn into_lower(self) -> lwip::TcpListener {
        self.lower
    }

    pub fn from_lower(waiter: Waiter<'a>, inner: lwip::TcpListener) -> TcpListener {
        TcpListener { waiter: waiter, lower: inner }
    }

    pub fn accept(&self) -> Result<(TcpStream, SocketAddr)> {
        try!(self.waiter.tcp_acceptable(&self.lower));
        let stream_lower = self.lower.try_accept().unwrap();
        let addr = SocketAddr::new(IP_ANY, 0); // FIXME: coax lwip into giving real addr here
        Ok((TcpStream {
            waiter: self.waiter,
            lower:  stream_lower,
            buffer: None
        }, addr))
    }

    pub fn acceptable(&self) -> bool {
        self.lower.state().borrow().acceptable()
    }

    pub fn keepalive(&self) -> bool {
        self.lower.keepalive()
    }

    pub fn set_keepalive(&self, keepalive: bool) {
        self.lower.set_keepalive(keepalive)
    }
}

pub use lwip::Shutdown;

pub struct TcpStreamInner(lwip::TcpStream, Option<(lwip::Pbuf<'static>, usize)>);

#[derive(Debug)]
pub struct TcpStream<'a> {
    waiter: Waiter<'a>,
    lower:  lwip::TcpStream,
    buffer: Option<(lwip::Pbuf<'static>, usize)>
}

impl<'a> TcpStream<'a> {
    pub fn into_lower(self) -> TcpStreamInner {
        TcpStreamInner(self.lower, self.buffer)
    }

    pub fn from_lower(waiter: Waiter<'a>, inner: TcpStreamInner) -> TcpStream {
        TcpStream { waiter: waiter, lower: inner.0, buffer: inner.1 }
    }

    pub fn shutdown(&self, how: Shutdown) -> Result<()> {
        Ok(try!(self.lower.shutdown(how)))
    }

    pub fn readable(&self) -> bool {
        self.buffer.is_some() || self.lower.state().borrow().readable()
    }

    pub fn writeable(&self) -> bool {
        self.lower.state().borrow().writeable()
    }
}

impl<'a> Read for TcpStream<'a> {
    fn read(&mut self, buf: &mut [u8]) -> Result<usize> {
        if self.buffer.is_none() {
            try!(self.waiter.tcp_readable(&self.lower));
            match self.lower.try_read() {
                Ok(Some(pbuf)) => self.buffer = Some((pbuf, 0)),
                Ok(None) => unreachable!(),
                Err(lwip::Error::ConnectionClosed) => return Ok(0),
                Err(err) => return Err(Error::from(err))
            }
        }

        let (pbuf, pos) = self.buffer.take().unwrap();
        let slice = &pbuf.as_slice()[pos..];
        let len = ::std::cmp::min(buf.len(), slice.len());
        buf[..len].copy_from_slice(&slice[..len]);
        if len < slice.len() {
            self.buffer = Some((pbuf, pos + len))
        }
        Ok(len)
    }
}

impl<'a> Write for TcpStream<'a> {
    fn write(&mut self, buf: &[u8]) -> Result<usize> {
        try!(self.waiter.tcp_writeable(&self.lower));
        Ok(try!(self.lower.write_in_place(buf,
                    || self.waiter.relinquish()
                                  .map_err(|_| lwip::Error::Interrupted))))
    }

    fn flush(&mut self) -> Result<()> {
        Ok(try!(self.lower.flush()))
    }
}
