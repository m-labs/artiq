#![allow(dead_code)]

use std::mem;
use std::cell::{Cell, RefCell, RefMut};
use std::vec::Vec;
use std::io::{Read, Write, Result, Error, ErrorKind};
use fringe::OwnedStack;
use fringe::generator::{Generator, Yielder, State as GeneratorState};

use smoltcp::wire::IpEndpoint;
use smoltcp::socket::{AsSocket, SocketHandle};
type SocketSet = ::smoltcp::socket::SocketSet<'static, 'static, 'static>;

use board;
use urc::Urc;

#[derive(Debug)]
struct WaitRequest {
    event:   Option<*const (Fn() -> bool + 'static)>,
    timeout: Option<u64>
}

unsafe impl Send for WaitRequest {}

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

impl Thread {
    unsafe fn new<F>(io: &Io, stack_size: usize, f: F) -> ThreadHandle
            where F: 'static + FnOnce(Io) + Send {
        let spawned = io.spawned.clone();
        let sockets = io.sockets.clone();

        let stack = OwnedStack::new(stack_size);
        ThreadHandle::new(Thread {
            generator: Generator::unsafe_new(stack, |yielder, _| {
                f(Io {
                    yielder: Some(yielder),
                    spawned: spawned,
                    sockets: sockets
                })
            }),
            waiting_for: WaitRequest {
                event:   None,
                timeout: None
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

#[derive(Clone)]
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

pub struct Scheduler {
    threads: Vec<ThreadHandle>,
    spawned: Urc<RefCell<Vec<ThreadHandle>>>,
    sockets: Urc<RefCell<SocketSet>>,
    run_idx: usize,
}

impl Scheduler {
    pub fn new() -> Scheduler {
        Scheduler {
            threads: Vec::new(),
            spawned: Urc::new(RefCell::new(Vec::new())),
            sockets: Urc::new(RefCell::new(SocketSet::new(Vec::new()))),
            run_idx: 0,
        }
    }

    pub fn io(&self) -> Io<'static> {
        Io {
            yielder: None,
            spawned: self.spawned.clone(),
            sockets: self.sockets.clone()
        }
    }

    pub fn run(&mut self) {
        self.sockets.borrow_mut().prune();

        self.threads.append(&mut *borrow_mut!(self.spawned));
        if self.threads.len() == 0 { return }

        let now = board::clock::get_ms();
        let start_idx = self.run_idx;
        loop {
            self.run_idx = (self.run_idx + 1) % self.threads.len();

            let result = {
                let mut thread = borrow_mut!(self.threads[self.run_idx].0);
                match thread.waiting_for {
                    _ if thread.interrupted => {
                        thread.interrupted = false;
                        thread.generator.resume(WaitResult::Interrupted)
                    }
                    WaitRequest { event: None, timeout: None } =>
                        thread.generator.resume(WaitResult::Completed),
                    WaitRequest { timeout: Some(instant), .. } if now >= instant =>
                        thread.generator.resume(WaitResult::TimedOut),
                    WaitRequest { event: Some(event), .. } if unsafe { (*event)() } =>
                        thread.generator.resume(WaitResult::Completed),
                    _ => {
                        if self.run_idx == start_idx {
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
                    self.threads.remove(self.run_idx);
                    self.run_idx = 0
                },
                Some(wait_request) => {
                    // The thread has suspended itself.
                    let mut thread = borrow_mut!(self.threads[self.run_idx].0);
                    thread.waiting_for = wait_request
                }
            }

            break
        }
    }

    pub fn sockets(&self) -> &RefCell<SocketSet> {
        &*self.sockets
    }
}

#[derive(Clone)]
pub struct Io<'a> {
    yielder: Option<&'a Yielder<WaitResult, WaitRequest, OwnedStack>>,
    spawned: Urc<RefCell<Vec<ThreadHandle>>>,
    sockets: Urc<RefCell<SocketSet>>,
}

impl<'a> Io<'a> {
    pub fn spawn<F>(&self, stack_size: usize, f: F) -> ThreadHandle
            where F: 'static + FnOnce(Io) + Send {
        let handle = unsafe { Thread::new(self, stack_size, f) };
        borrow_mut!(self.spawned).push(handle.clone());
        handle
    }

    fn yielder(&self) -> &'a Yielder<WaitResult, WaitRequest, OwnedStack> {
        self.yielder.expect("cannot suspend the scheduler thread")
    }

    pub fn sleep(&self, duration_ms: u64) -> Result<()> {
        let request = WaitRequest {
            timeout: Some(board::clock::get_ms() + duration_ms),
            event:   None
        };

        match self.yielder().suspend(request) {
            WaitResult::TimedOut => Ok(()),
            WaitResult::Interrupted => Err(Error::new(ErrorKind::Interrupted, "")),
            _ => unreachable!()
        }
    }

    fn suspend(&self, request: WaitRequest) -> Result<()> {
        match self.yielder().suspend(request) {
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

    pub fn until<F: Fn() -> bool + 'static>(&self, f: F) -> Result<()> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(&f as *const _)
        })
    }

    pub fn join(&self, handle: ThreadHandle) -> Result<()> {
        self.until(move || handle.terminated())
    }
}

macro_rules! until {
    ($socket:expr, $ty:ty, |$var:ident| $cond:expr) => ({
        let (sockets, handle) = ($socket.io.sockets.clone(), $socket.handle);
        $socket.io.until(move || {
            let mut sockets = borrow_mut!(sockets);
            let $var: &mut $ty = sockets.get_mut(handle).as_socket();
            $cond
        })
    })
}

use ::smoltcp::Error as ErrorLower;
// https://github.com/rust-lang/rust/issues/44057
// type ErrorLower = ::smoltcp::Error;

type UdpPacketBuffer = ::smoltcp::socket::UdpPacketBuffer<'static>;
type UdpSocketBuffer = ::smoltcp::socket::UdpSocketBuffer<'static, 'static>;
type UdpSocketLower  = ::smoltcp::socket::UdpSocket<'static, 'static>;

pub struct UdpSocket<'a> {
    io:     &'a Io<'a>,
    handle: SocketHandle
}

impl<'a> UdpSocket<'a> {
    pub fn new(io: &'a Io<'a>, buffer_depth: usize, buffer_width: usize) -> UdpSocket<'a> {
        let mut rx_buffer = vec![];
        let mut tx_buffer = vec![];
        for _ in 0..buffer_depth {
            rx_buffer.push(UdpPacketBuffer::new(vec![0; buffer_width]));
            tx_buffer.push(UdpPacketBuffer::new(vec![0; buffer_width]));
        }
        let handle = borrow_mut!(io.sockets)
                        .add(UdpSocketLower::new(
                                UdpSocketBuffer::new(rx_buffer),
                                UdpSocketBuffer::new(tx_buffer)));
        UdpSocket {
            io:     io,
            handle: handle
        }
    }

    fn as_lower<'b>(&'b self) -> RefMut<'b, UdpSocketLower> {
        RefMut::map(borrow_mut!(self.io.sockets),
                    |sockets| sockets.get_mut(self.handle).as_socket())
    }

    pub fn bind<T: Into<IpEndpoint>>(&self, endpoint: T) -> Result<()> {
        match self.as_lower().bind(endpoint) {
            Ok(()) => Ok(()),
            Err(ErrorLower::Illegal) =>
                Err(Error::new(ErrorKind::Other, "already listening")),
            Err(ErrorLower::Unaddressable) =>
                Err(Error::new(ErrorKind::AddrNotAvailable, "port cannot be zero")),
            _ => unreachable!()
        }
    }

    pub fn recv_from(&self, buf: &mut [u8]) -> Result<(usize, IpEndpoint)> {
        until!(self, UdpSocketLower, |s| s.can_recv())?;
        match self.as_lower().recv_slice(buf) {
            Ok(result) => Ok(result),
            Err(_) => unreachable!()
        }
    }

    pub fn send_to(&self, buf: &[u8], addr: IpEndpoint) -> Result<()> {
        until!(self, UdpSocketLower, |s| s.can_send())?;
        match self.as_lower().send_slice(buf, addr) {
            Ok(()) => Ok(()),
            Err(ErrorLower::Unaddressable) =>
                Err(Error::new(ErrorKind::AddrNotAvailable, "unaddressable destination")),
            Err(ErrorLower::Truncated) =>
                Err(Error::new(ErrorKind::Other, "packet does not fit in buffer")),
            Err(_) => unreachable!()
        }
    }
}

impl<'a> Drop for UdpSocket<'a> {
    fn drop(&mut self) {
        borrow_mut!(self.io.sockets).release(self.handle)
    }
}

type TcpSocketBuffer = ::smoltcp::socket::TcpSocketBuffer<'static>;
type TcpSocketLower  = ::smoltcp::socket::TcpSocket<'static>;

pub struct TcpSocketHandle(SocketHandle);

pub struct TcpListener<'a> {
    io:          &'a Io<'a>,
    handle:      Cell<SocketHandle>,
    buffer_size: Cell<usize>,
    endpoint:    Cell<IpEndpoint>
}

impl<'a> TcpListener<'a> {
    fn new_lower(io: &'a Io<'a>, buffer_size: usize) -> SocketHandle {
        let rx_buffer = vec![0; buffer_size];
        let tx_buffer = vec![0; buffer_size];
        borrow_mut!(io.sockets)
            .add(TcpSocketLower::new(
                TcpSocketBuffer::new(rx_buffer),
                TcpSocketBuffer::new(tx_buffer)))
    }

    pub fn new(io: &'a Io<'a>, buffer_size: usize) -> TcpListener<'a> {
        TcpListener {
            io:          io,
            handle:      Cell::new(Self::new_lower(io, buffer_size)),
            buffer_size: Cell::new(buffer_size),
            endpoint:    Cell::new(IpEndpoint::default())
        }
    }

    fn as_lower<'b>(&'b self) -> RefMut<'b, TcpSocketLower> {
        RefMut::map(borrow_mut!(self.io.sockets),
                    |sockets| sockets.get_mut(self.handle.get()).as_socket())
    }

    pub fn is_open(&self) -> bool {
        self.as_lower().is_open()
    }

    pub fn can_accept(&self) -> bool {
        self.as_lower().is_active()
    }

    pub fn local_endpoint(&self) -> IpEndpoint {
        self.as_lower().local_endpoint()
    }

    pub fn listen<T: Into<IpEndpoint>>(&self, endpoint: T) -> Result<()> {
        let endpoint = endpoint.into();
        match self.as_lower().listen(endpoint) {
            Ok(()) => Ok(()),
            Err(ErrorLower::Illegal) =>
                Err(Error::new(ErrorKind::Other, "already listening")),
            Err(ErrorLower::Unaddressable) =>
                Err(Error::new(ErrorKind::InvalidInput, "port cannot be zero")),
            _ => unreachable!()
        }?;
        self.endpoint.set(endpoint);
        Ok(())
    }

    pub fn accept(&self) -> Result<TcpStream<'a>> {
        // We're waiting until at least one half of the connection becomes open.
        // This handles the case where a remote socket immediately sends a FIN--
        // that still counts as accepting even though nothing may be sent.
        let (sockets, handle) = (self.io.sockets.clone(), self.handle.get());
        self.io.until(move || {
            let mut sockets = borrow_mut!(sockets);
            let socket: &mut TcpSocketLower = sockets.get_mut(handle).as_socket();
            socket.may_send() || socket.may_recv()
        })?;

        let accepted = self.handle.get();
        self.handle.set(Self::new_lower(self.io, self.buffer_size.get()));
        match self.listen(self.endpoint.get()) {
            Ok(()) => (),
            _ => unreachable!()
        }
        Ok(TcpStream {
            io:     self.io,
            handle: accepted
        })
    }

    pub fn close(&self) {
        self.as_lower().close()
    }
}

impl<'a> Drop for TcpListener<'a> {
    fn drop(&mut self) {
        self.as_lower().close();
        borrow_mut!(self.io.sockets).release(self.handle.get())
    }
}

pub struct TcpStream<'a> {
    io:     &'a Io<'a>,
    handle: SocketHandle
}

impl<'a> TcpStream<'a> {
    pub fn into_handle(self) -> TcpSocketHandle {
        let handle = self.handle;
        mem::forget(self);
        TcpSocketHandle(handle)
    }

    pub fn from_handle(io: &'a Io<'a>, handle: TcpSocketHandle) -> TcpStream<'a> {
        TcpStream {
            io:     io,
            handle: handle.0
        }
    }

    fn as_lower<'b>(&'b self) -> RefMut<'b, TcpSocketLower> {
        RefMut::map(borrow_mut!(self.io.sockets),
                    |sockets| sockets.get_mut(self.handle).as_socket())
    }

    pub fn is_open(&self) -> bool {
        self.as_lower().is_open()
    }

    pub fn may_send(&self) -> bool {
        self.as_lower().may_send()
    }

    pub fn may_recv(&self) -> bool {
        self.as_lower().may_recv()
    }

    pub fn can_send(&self) -> bool {
        self.as_lower().can_send()
    }

    pub fn can_recv(&self) -> bool {
        self.as_lower().can_recv()
    }

    pub fn local_endpoint(&self) -> IpEndpoint {
        self.as_lower().local_endpoint()
    }

    pub fn remote_endpoint(&self) -> IpEndpoint {
        self.as_lower().remote_endpoint()
    }

    pub fn close(&self) -> Result<()> {
        self.as_lower().close();
        until!(self, TcpSocketLower, |s| !s.is_open())?;
        // right now the socket may be in TIME-WAIT state. if we don't give it a chance to send
        // a packet, and the user code executes a loop { s.listen(); s.read(); s.close(); }
        // then the last ACK will never be sent.
        self.io.relinquish()
    }
}

impl<'a> Read for TcpStream<'a> {
    fn read(&mut self, buf: &mut [u8]) -> Result<usize> {
        // Only borrow the underlying socket for the span of the next statement.
        let result = self.as_lower().recv_slice(buf);
        match result {
            // Slow path: we need to block until buffer is non-empty.
            Ok(0) => {
                until!(self, TcpSocketLower, |s| s.can_recv() || !s.may_recv())?;
                match self.as_lower().recv_slice(buf) {
                    Ok(length) => Ok(length),
                    Err(ErrorLower::Illegal) => Ok(0),
                    _ => unreachable!()
                }
            }
            // Fast path: we had data in buffer.
            Ok(length) => Ok(length),
            // Error path: the receive half of the socket is not open.
            Err(ErrorLower::Illegal) => Ok(0),
            // No other error may be returned.
            Err(_) => unreachable!()
        }
    }
}

impl<'a> Write for TcpStream<'a> {
    fn write(&mut self, buf: &[u8]) -> Result<usize> {
        // Only borrow the underlying socket for the span of the next statement.
        let result = self.as_lower().send_slice(buf);
        match result {
            // Slow path: we need to block until buffer is non-full.
            Ok(0) => {
                until!(self, TcpSocketLower, |s| s.can_send() || !s.may_send())?;
                match self.as_lower().send_slice(buf) {
                    Ok(length) => Ok(length),
                    Err(ErrorLower::Illegal) => Ok(0),
                    _ => unreachable!()
                }
            }
            // Fast path: we had space in buffer.
            Ok(length) => Ok(length),
            // Error path: the transmit half of the socket is not open.
            Err(ErrorLower::Illegal) => Ok(0),
            // No other error may be returned.
            Err(_) => unreachable!()
        }
    }

    fn flush(&mut self) -> Result<()> {
        // smoltcp always sends all available data when it's possible; nothing to do
        Ok(())
    }
}

impl<'a> Drop for TcpStream<'a> {
    fn drop(&mut self) {
        self.as_lower().close();
        borrow_mut!(self.io.sockets).release(self.handle)
    }
}
