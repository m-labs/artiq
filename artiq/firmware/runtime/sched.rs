#![allow(dead_code)]

use core::mem;
use core::result;
use core::cell::{Cell, RefCell, RefMut};
use alloc::vec::Vec;
use fringe::OwnedStack;
use fringe::generator::{Generator, Yielder, State as GeneratorState};
use smoltcp::time::Duration;
use smoltcp::Error as NetworkError;
use smoltcp::wire::{IpEndpoint, Ipv4Cidr};
use smoltcp::iface::{Interface, SocketHandle};

use io::{Read, Write};
use board_misoc::clock;
use urc::Urc;
use board_misoc::ethmac::EthernetDevice;
use smoltcp::phy::Tracer;
use ip_addr_storage::InterfaceEx;

#[derive(Fail, Debug)]
pub enum Error {
    #[fail(display = "interrupted")]
    Interrupted,
    #[fail(display = "timed out")]
    TimedOut,
    #[fail(display = "network error: {}", _0)]
    Network(NetworkError)
}

impl From<NetworkError> for Error {
    fn from(value: NetworkError) -> Error {
        Error::Network(value)
    }
}

#[derive(Debug)]
struct WaitRequest {
    event:   Option<*mut dyn FnMut() -> bool>,
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
    generator:   Generator<'static, WaitResult, WaitRequest, OwnedStack>,
    waiting_for: WaitRequest,
    interrupted: bool
}

impl Thread {
    unsafe fn new<F>(io: &Io, stack_size: usize, f: F) -> ThreadHandle
            where F: 'static + FnOnce(Io) + Send {
        let spawned = io.spawned.clone();
        let network = io.network.clone();

        // Add a 4k stack guard to the stack of any new threads
        let stack = OwnedStack::new(stack_size + 4096);
        ThreadHandle::new(Thread {
            generator: Generator::unsafe_new(stack, |yielder, _| {
                f(Io {
                    yielder: Some(yielder),
                    spawned,
                    network
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

type Network = Interface<'static, Tracer<EthernetDevice>>;

pub struct Scheduler {
    threads: Vec<ThreadHandle>,
    spawned: Urc<RefCell<Vec<ThreadHandle>>>,
    network: Urc<RefCell<Network>>,
    run_idx: usize,
}

impl Scheduler {
    pub fn new(network: Network) -> Scheduler {
        Scheduler {
            threads: Vec::new(),
            spawned: Urc::new(RefCell::new(Vec::new())),
            network: Urc::new(RefCell::new(network)),
            run_idx: 0,
        }
    }

    pub fn io(&self) -> Io<'static> {
        Io {
            yielder: None,
            spawned: self.spawned.clone(),
            network: self.network.clone()
        }
    }

    pub fn run(&mut self) {
        self.threads.append(&mut *self.spawned.borrow_mut());
        if self.threads.len() == 0 { return }

        let now = clock::get_ms();
        let start_idx = self.run_idx;
        loop {
            self.run_idx = (self.run_idx + 1) % self.threads.len();

            let result = {
                let &mut Thread { ref mut generator, ref mut interrupted, ref waiting_for } =
                    &mut *self.threads[self.run_idx].0.borrow_mut();
                if *interrupted {
                    *interrupted = false;
                    generator.resume(WaitResult::Interrupted)
                } else if waiting_for.event.is_none() && waiting_for.timeout.is_none() {
                    generator.resume(WaitResult::Completed)
                } else if waiting_for.timeout.map(|instant| now >= instant).unwrap_or(false) {
                    generator.resume(WaitResult::TimedOut)
                } else if waiting_for.event.map(|event| unsafe { (*event)() }).unwrap_or(false) {
                    generator.resume(WaitResult::Completed)
                } else if self.run_idx == start_idx {
                    // We've checked every thread and none of them are runnable.
                    break
                } else {
                    continue
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
                    let mut thread = self.threads[self.run_idx].0.borrow_mut();
                    thread.waiting_for = wait_request
                }
            }

            break
        }
    }

    pub fn run_network(&mut self) {
        let mut interface = self.network.borrow_mut();
        loop {
            let timestamp = smoltcp::time::Instant::from_millis(clock::get_ms() as i64);
            match interface.poll(timestamp) {
                Ok(true) => (),
                Ok(false) => break,
                Err(smoltcp::Error::Unrecognized) => (),
                Err(err) => debug!("network error: {}", err)
            }
        }
    }
}

#[derive(Clone)]
pub struct Io<'a> {
    yielder: Option<&'a Yielder<WaitResult, WaitRequest>>,
    spawned: Urc<RefCell<Vec<ThreadHandle>>>,
    network: Urc<RefCell<Network>>,
}

impl<'a> Io<'a> {
    pub fn spawn<F>(&self, stack_size: usize, f: F) -> ThreadHandle
            where F: 'static + FnOnce(Io) + Send {
        let handle = unsafe { Thread::new(self, stack_size, f) };
        self.spawned.borrow_mut().push(handle.clone());
        handle
    }

    fn yielder(&self) -> &'a Yielder<WaitResult, WaitRequest> {
        self.yielder.expect("cannot suspend the scheduler thread")
    }

    pub fn sleep(&self, duration_ms: u64) -> Result<(), Error> {
        let request = WaitRequest {
            timeout: Some(clock::get_ms() + duration_ms),
            event:   None
        };

        match self.yielder().suspend(request) {
            WaitResult::TimedOut => Ok(()),
            WaitResult::Interrupted => Err(Error::Interrupted),
            _ => unreachable!()
        }
    }

    fn suspend(&self, request: WaitRequest) -> Result<(), Error> {
        match self.yielder().suspend(request) {
            WaitResult::Completed => Ok(()),
            WaitResult::TimedOut => Err(Error::TimedOut),
            WaitResult::Interrupted => Err(Error::Interrupted)
        }
    }

    pub fn relinquish(&self) -> Result<(), Error> {
        self.suspend(WaitRequest {
            timeout: None,
            event:   None
        })
    }

    pub fn until<F: FnMut() -> bool>(&self, mut f: F) -> Result<(), Error> {
        let f = unsafe { mem::transmute::<&mut dyn FnMut() -> bool, *mut dyn FnMut() -> bool>(&mut f) };
        self.suspend(WaitRequest {
            timeout: None,
            event:   Some(f)
        })
    }

    pub fn until_ok<T, E, F>(&self, mut f: F) -> Result<T, Error>
        where F: FnMut() -> result::Result<T, E>
    {
        let mut value = None;
        self.until(|| {
            if let Ok(result) = f() {
                value = Some(result)
            }
            value.is_some()
        })?;
        Ok(value.unwrap())
    }

    pub fn join(&self, handle: ThreadHandle) -> Result<(), Error> {
        self.until(move || handle.terminated())
    }

    pub fn set_ipv4_address(&self, addr: &Ipv4Cidr) {
        self.network.borrow_mut().update_ipv4_addr(addr)
    }
}

#[derive(Clone)]
pub struct Mutex(Urc<Cell<bool>>);

impl Mutex {
    pub fn new() -> Mutex {
        Mutex(Urc::new(Cell::new(false)))
    }

    pub fn lock<'a>(&'a self, io: &Io) -> Result<MutexGuard<'a>, Error> {
        io.until(|| !self.0.get())?;
        self.0.set(true);
        Ok(MutexGuard(&*self.0))
    }
}

pub struct MutexGuard<'a>(&'a Cell<bool>);

impl<'a> Drop for MutexGuard<'a> {
    fn drop(&mut self) {
        self.0.set(false)
    }
}

macro_rules! until {
    ($socket:expr, $ty:ty, |$var:ident| $cond:expr) => ({
        let (network, handle) = ($socket.io.network.clone(), $socket.handle);
        $socket.io.until(move || {
            let mut network = network.borrow_mut();
            let $var = network.get_socket::<$ty>(handle);
            $cond
        })
    })
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
        io.network
            .borrow_mut()
            .add_socket(TcpSocketLower::new(
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

    fn with_lower<F, R>(&self, f: F) -> R
            where F: FnOnce(&mut TcpSocketLower) -> R {
        let mut network = self.io.network.borrow_mut();
        let result = f(network.get_socket(self.handle.get()));
        result
    }

    pub fn is_open(&self) -> bool {
        self.with_lower(|s| s.is_open())
    }

    pub fn can_accept(&self) -> bool {
        self.with_lower(|s| s.is_active())
    }

    pub fn local_endpoint(&self) -> IpEndpoint {
        self.with_lower(|s| s.local_endpoint())
    }

    pub fn listen<T: Into<IpEndpoint>>(&self, endpoint: T) -> Result<(), Error> {
        let endpoint = endpoint.into();
        self.with_lower(|s| s.listen(endpoint))
            .map(|()| {
                self.endpoint.set(endpoint);
                ()
            })
            .map_err(|err| err.into())
    }

    /// Accept a TCP connection
    ///
    /// When the returned TcpStream is dropped it is immediately forgotten about. In order to
    /// ensure that pending data is sent and the far end is notified, `close` must be called.
    pub fn accept(&self) -> Result<TcpStream<'a>, Error> {
        // We're waiting until at least one half of the connection becomes open.
        // This handles the case where a remote socket immediately sends a FIN--
        // that still counts as accepting even though nothing may be sent.
        let (network, handle) = (self.io.network.clone(), self.handle.get());
        self.io.until(move || {
            let mut network = network.borrow_mut();
            let socket = network.get_socket::<TcpSocketLower>(handle);
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
        self.with_lower(|s| s.close())
    }
}

impl<'a> Drop for TcpListener<'a> {
    fn drop(&mut self) {
        self.with_lower(|s| s.close());
        self.io.network.borrow_mut().remove_socket(self.handle.get());
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

    fn with_lower<F, R>(&self, f: F) -> R
            where F: FnOnce(&mut TcpSocketLower) -> R {
        let mut network = self.io.network.borrow_mut();
        let result = f(network.get_socket(self.handle));
        result
    }

    pub fn is_open(&self) -> bool {
        self.with_lower(|s| s.is_open())
    }

    pub fn may_send(&self) -> bool {
        self.with_lower(|s| s.may_send())
    }

    pub fn may_recv(&self) -> bool {
        self.with_lower(|s| s.may_recv())
    }

    pub fn can_send(&self) -> bool {
        self.with_lower(|s| s.can_send())
    }

    pub fn can_recv(&self) -> bool {
        self.with_lower(|s| s.can_recv())
    }

    pub fn local_endpoint(&self) -> IpEndpoint {
        self.with_lower(|s| s.local_endpoint())
    }

    pub fn remote_endpoint(&self) -> IpEndpoint {
        self.with_lower(|s| s.remote_endpoint())
    }

    pub fn timeout(&self) -> Option<u64> {
        self.with_lower(|s| s.timeout().as_ref().map(Duration::millis))
    }

    pub fn set_timeout(&self, value: Option<u64>) {
        self.with_lower(|s| s.set_timeout(value.map(Duration::from_millis)))
    }

    pub fn keep_alive(&self) -> Option<u64> {
        self.with_lower(|s| s.keep_alive().as_ref().map(Duration::millis))
    }

    pub fn set_keep_alive(&self, value: Option<u64>) {
        self.with_lower(|s| s.set_keep_alive(value.map(Duration::from_millis)))
    }

    pub fn close(&self) -> Result<(), Error> {
        self.with_lower(|s| s.close());
        until!(self, TcpSocketLower, |s| !s.is_open())?;
        // right now the socket may be in TIME-WAIT state. if we don't give it a chance to send
        // a packet, and the user code executes a loop { s.listen(); s.read(); s.close(); }
        // then the last ACK will never be sent.
        self.io.relinquish()
    }
}

impl<'a> Read for TcpStream<'a> {
    type ReadError = Error;

    fn read(&mut self, buf: &mut [u8]) -> Result<usize, Self::ReadError> {
        // Only borrow the underlying socket for the span of the next statement.
        let result = self.with_lower(|s| s.recv_slice(buf));
        match result {
            // Slow path: we need to block until buffer is non-empty.
            Ok(0) => {
                until!(self, TcpSocketLower, |s| s.can_recv() || !s.may_recv())?;
                match self.with_lower(|s| s.recv_slice(buf)) {
                    Ok(length) => Ok(length),
                    Err(NetworkError::Finished) |
                    Err(NetworkError::Illegal) => Ok(0),
                    Err(e) => {
                        panic!("Unexpected error from smoltcp: {}", e);
                    }
                }
            }
            // Fast path: we had data in buffer.
            Ok(length) => Ok(length),
            // We've received a fin.
            Err(NetworkError::Finished) |
            // Error path: the receive half of the socket is not open.
            Err(NetworkError::Illegal) => Ok(0),
            // No other error may be returned.
            Err(e) => {
                // This could return Err(Error::Network(e)) rather than panic,
                // but I expect that'll just cause a panic later perhaps with
                // less interesting context.
                panic!("Unexpected error from smoltcp: {}", e);
            }
        }
    }
}

impl<'a> Write for TcpStream<'a> {
    type WriteError = Error;
    type FlushError = Error;

    fn write(&mut self, buf: &[u8]) -> Result<usize, Self::WriteError> {
        // Only borrow the underlying socket for the span of the next statement.
        let result = self.with_lower(|s| s.send_slice(buf));
        match result {
            // Slow path: we need to block until buffer is non-full.
            Ok(0) => {
                until!(self, TcpSocketLower, |s| s.can_send() || !s.may_send())?;
                match self.with_lower(|s| s.send_slice(buf)) {
                    Ok(length) => Ok(length),
                    Err(NetworkError::Illegal) => Ok(0),
                    _ => unreachable!()
                }
            }
            // Fast path: we had space in buffer.
            Ok(length) => Ok(length),
            // Error path: the transmit half of the socket is not open.
            Err(NetworkError::Illegal) => Ok(0),
            // No other error may be returned.
            Err(_) => unreachable!()
        }
    }

    fn flush(&mut self) -> Result<(), Self::FlushError> {
        until!(self, TcpSocketLower, |s|  s.send_queue() == 0 || !s.may_send())?;
        if self.with_lower(|s| s.send_queue()) == 0 {
            Ok(())
        } else {
            Err(Error::Network(NetworkError::Illegal))
        }
    }
}

impl<'a> Drop for TcpStream<'a> {
    fn drop(&mut self) {
        // There's no point calling the lower close here unless we also defer the removal of the
        // socket from smoltcp until it's had a chance to process the event
        let (unsent_bytes, is_open) = self.with_lower(
            |s| (s.send_queue(), s.is_open())
        );
        if is_open {
            warn!(
                "Dropping open TcpStream in state {}, with {} unsent bytes",
                self.with_lower(|s| s.state()), unsent_bytes
            )
        } else if unsent_bytes != 0 {
            debug!("Dropping socket with {} bytes unsent", unsent_bytes)
        }

        self.io.network.borrow_mut().remove_socket(self.handle);
    }
}

pub struct Dhcpv4Socket<'a> {
    io: &'a Io<'a>,
    handle: SocketHandle,
}

impl<'a> Dhcpv4Socket<'a> {

    fn new_lower(io: &'a Io<'a>) -> SocketHandle {
        let socket = smoltcp::socket::Dhcpv4Socket::new();
        io.network.borrow_mut().add_socket(socket)
    }

    pub fn new(io: &'a Io<'a>) -> Self {
        Self {
            io,
            handle: Self::new_lower(io)
        }
    }

    fn lower(&mut self) -> RefMut<smoltcp::socket::Dhcpv4Socket> {
        RefMut::map(
            self.io.network.borrow_mut(),
            |network| network.get_socket::<smoltcp::socket::Dhcpv4Socket>(self.handle),
        )
    }

    pub fn poll(&mut self) -> Option<smoltcp::socket::Dhcpv4Event> {
        self.lower().poll()
    }

    pub fn reset(&mut self) {
        self.lower().reset()
    }
}

impl<'a> Drop for Dhcpv4Socket<'a> {
    fn drop(&mut self) {
        let mut network = self.io.network.borrow_mut();
        network.remove_socket(self.handle);
    }
}
