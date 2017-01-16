#![allow(dead_code)]

use std::mem;
use std::cell::{RefCell, RefMut};
use std::vec::Vec;
use std::io::{Read, Write, Result, Error, ErrorKind};
use fringe::OwnedStack;
use fringe::generator::{Generator, Yielder, State as GeneratorState};

use smoltcp::wire::IpEndpoint;
use smoltcp::socket::AsSocket;
use smoltcp::socket::SocketHandle;
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
                    WaitRequest { event: Some(_), timeout: Some(instant) } if now >= instant =>
                        thread.generator.resume(WaitResult::TimedOut),
                    WaitRequest { event: None, timeout: Some(instant) } if now >= instant =>
                        thread.generator.resume(WaitResult::Completed),
                    WaitRequest { event: Some(event), timeout: _ } if unsafe { (*event)() } =>
                        thread.generator.resume(WaitResult::Completed),
                    WaitRequest { event: None, timeout: None } =>
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
            let $var = sockets.get_mut(handle).as_socket() as &mut $ty;
            $cond
        })
    })
}

type UdpPacketBuffer = ::smoltcp::socket::UdpPacketBuffer<'static>;
type UdpSocketBuffer = ::smoltcp::socket::UdpSocketBuffer<'static, 'static>;
type UdpSocketLower  = ::smoltcp::socket::UdpSocket<'static, 'static>;

pub struct UdpSocket<'a> {
    io:     &'a Io<'a>,
    handle: SocketHandle
}

impl<'a> UdpSocket<'a> {
    pub fn new(io: &'a Io<'a>, rx_buffer: UdpSocketBuffer, tx_buffer: UdpSocketBuffer) ->
            UdpSocket<'a> {
        let handle = borrow_mut!(io.sockets)
            .add(UdpSocketLower::new(rx_buffer, tx_buffer));
        UdpSocket {
            io:     io,
            handle: handle
        }
    }

    pub fn with_buffer_size(io: &'a Io<'a>, buffer_depth: usize, buffer_width: usize) ->
            UdpSocket<'a> {
        let mut rx_buffer = vec![];
        let mut tx_buffer = vec![];
        for _ in 0..buffer_depth {
            rx_buffer.push(UdpPacketBuffer::new(vec![0; buffer_width]));
            tx_buffer.push(UdpPacketBuffer::new(vec![0; buffer_width]));
        }
        Self::new(io,
            UdpSocketBuffer::new(rx_buffer),
            UdpSocketBuffer::new(tx_buffer))
    }

    fn as_lower<'b>(&'b self) -> RefMut<'b, UdpSocketLower> {
        RefMut::map(borrow_mut!(self.io.sockets),
                    |sockets| sockets.get_mut(self.handle).as_socket())
    }

    pub fn bind<T: Into<IpEndpoint>>(&self, endpoint: T) {
        self.as_lower().bind(endpoint)
    }

    pub fn recv_from(&self, buf: &mut [u8]) -> Result<(usize, IpEndpoint)> {
        try!(until!(self, UdpSocketLower, |s| s.can_recv()));
        match self.as_lower().recv_slice(buf) {
            Ok(r) => Ok(r),
            Err(()) => {
                // No data in the buffer--should never happen after the wait above.
                unreachable!()
            }
        }
    }

    pub fn send_to(&self, buf: &[u8], addr: IpEndpoint) -> Result<usize> {
        try!(until!(self, UdpSocketLower, |s| s.can_send()));
        match self.as_lower().send_slice(buf, addr) {
            Ok(r) => Ok(r),
            Err(()) => {
                // No space in the buffer--should never happen after the wait above.
                unreachable!()
            }
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

pub struct TcpSocket<'a> {
    io:     &'a Io<'a>,
    handle: SocketHandle
}

impl<'a> TcpSocket<'a> {
    pub fn new(io: &'a Io<'a>, rx_buffer: TcpSocketBuffer, tx_buffer: TcpSocketBuffer) ->
            TcpSocket<'a> {
        let handle = borrow_mut!(io.sockets)
            .add(TcpSocketLower::new(rx_buffer, tx_buffer));
        TcpSocket {
            io:     io,
            handle: handle
        }
    }

    pub fn with_buffer_size(io: &'a Io<'a>, buffer_size: usize) -> TcpSocket<'a> {
        let rx_buffer = vec![0; buffer_size];
        let tx_buffer = vec![0; buffer_size];
        Self::new(io,
            TcpSocketBuffer::new(rx_buffer),
            TcpSocketBuffer::new(tx_buffer))
    }

    pub fn into_handle(self) -> TcpSocketHandle {
        let handle = self.handle;
        mem::forget(self);
        TcpSocketHandle(handle)
    }

    pub fn from_handle(io: &'a Io<'a>, handle: TcpSocketHandle) -> TcpSocket<'a> {
        TcpSocket {
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

    pub fn is_listening(&self) -> bool {
        self.as_lower().is_listening()
    }

    pub fn is_active(&self) -> bool {
        self.as_lower().is_active()
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

    pub fn listen<T: Into<IpEndpoint>>(&self, endpoint: T) -> Result<()> {
        self.as_lower().listen(endpoint)
            .map_err(|()| Error::new(ErrorKind::Other,
                                     "cannot listen: already connected"))
    }

    pub fn accept(&self) -> Result<()> {
        // We're waiting until at least one half of the connection becomes open.
        // This handles the case where a remote socket immediately sends a FIN--
        // that still counts as accepting even though nothing may be sent.
        until!(self, TcpSocketLower, |s| s.may_send() || s.may_recv())
    }

    pub fn close(&self) -> Result<()> {
        self.as_lower().close();
        try!(until!(self, TcpSocketLower, |s| !s.is_open()));
        // right now the socket may be in TIME-WAIT state. if we don't give it a chance to send
        // a packet, and the user code executes a loop { s.listen(); s.read(); s.close(); }
        // then the last ACK will never be sent.
        self.io.relinquish()
    }
}

impl<'a> Read for TcpSocket<'a> {
    fn read(&mut self, buf: &mut [u8]) -> Result<usize> {
        // fast path
        let result = self.as_lower().recv_slice(buf);
        match result {
            Ok(0) | Err(()) => {
                // slow path
                if !self.as_lower().may_recv() { return Ok(0) }
                try!(until!(self, TcpSocketLower, |s| s.can_recv()));
                Ok(self.as_lower().recv_slice(buf)
                       .expect("may_recv implies that data was available"))
            }
            Ok(length) => Ok(length)
        }
    }
}

impl<'a> Write for TcpSocket<'a> {
    fn write(&mut self, buf: &[u8]) -> Result<usize> {
        // fast path
        let result = self.as_lower().send_slice(buf);
        match result {
            Ok(0) | Err(()) => {
                // slow path
                if !self.as_lower().may_send() { return Ok(0) }
                try!(until!(self, TcpSocketLower, |s| s.can_send()));
                Ok(self.as_lower().send_slice(buf)
                       .expect("may_send implies that data was available"))
            }
            Ok(length) => Ok(length)
        }
    }

    fn flush(&mut self) -> Result<()> {
        // smoltcp always sends all available data when it's possible; nothing to do
        Ok(())
    }
}

impl<'a> Drop for TcpSocket<'a> {
    fn drop(&mut self) {
        if self.is_open() {
            // scheduler will remove any closed sockets with zero references.
            self.as_lower().close()
        }
        borrow_mut!(self.io.sockets).release(self.handle)
    }
}
