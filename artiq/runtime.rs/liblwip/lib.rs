#![feature(alloc, collections, libc)]
#![no_std]

extern crate alloc;
extern crate collections;
extern crate libc;
extern crate lwip_sys;
extern crate std_artiq as std;

use core::marker::PhantomData;
use core::cell::RefCell;
use alloc::boxed::Box;
use collections::LinkedList;
use libc::c_void;
use std::error;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    OutOfMemory,
    Buffer,
    Timeout,
    Routing,
    InProgress,
    IllegalValue,
    WouldBlock,
    AddressInUse,
    AlreadyConnecting,
    AlreadyConnected,
    NotConnected,
    Interface,
    ConnectionAborted,
    ConnectionReset,
    ConnectionClosed,
    IllegalArgument,
}

impl Error {
    fn as_str(&self) -> &str {
        match *self {
            Error::OutOfMemory => "out of memory error",
            Error::Buffer => "buffer error",
            Error::Timeout => "timeout",
            Error::Routing => "routing error",
            Error::InProgress => "operation in progress",
            Error::IllegalValue => "illegal value",
            Error::WouldBlock => "operation would block",
            Error::AddressInUse => "address in use",
            Error::AlreadyConnecting => "already connecting",
            Error::AlreadyConnected => "already connected",
            Error::NotConnected => "not connected",
            Error::Interface => "low-level netif error",
            Error::ConnectionAborted => "connection aborted",
            Error::ConnectionReset => "connection reset",
            Error::ConnectionClosed => "connection closed",
            Error::IllegalArgument => "illegal argument",
        }
    }
}

impl core::fmt::Display for Error {
    fn fmt(&self, f: &mut core::fmt::Formatter) -> core::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

impl error::Error for Error {
    fn description(&self) -> &str {
        self.as_str()
    }
}

impl From<Error> for std::io::Error {
    fn from(lower: Error) -> std::io::Error {
        std::io::Error::new(std::io::ErrorKind::Other, lower)
    }
}

pub type Result<T> = core::result::Result<T, Error>;

fn result_from<T, F>(err: lwip_sys::err, f: F) -> Result<T>
        where F: FnOnce() -> T {
    match err {
        lwip_sys::ERR_OK => Ok(f()),
        lwip_sys::ERR_MEM => Err(Error::OutOfMemory),
        lwip_sys::ERR_BUF => Err(Error::Buffer),
        lwip_sys::ERR_TIMEOUT => Err(Error::Timeout),
        lwip_sys::ERR_RTE => Err(Error::Routing),
        lwip_sys::ERR_INPROGRESS => Err(Error::InProgress),
        lwip_sys::ERR_VAL => Err(Error::IllegalValue),
        lwip_sys::ERR_WOULDBLOCK => Err(Error::WouldBlock),
        lwip_sys::ERR_USE => Err(Error::AddressInUse),
        lwip_sys::ERR_ALREADY => Err(Error::AlreadyConnecting),
        lwip_sys::ERR_ISCONN => Err(Error::AlreadyConnected),
        lwip_sys::ERR_CONN => Err(Error::NotConnected),
        lwip_sys::ERR_IF => Err(Error::Interface),
        lwip_sys::ERR_ABRT => Err(Error::ConnectionAborted),
        lwip_sys::ERR_RST => Err(Error::ConnectionReset),
        lwip_sys::ERR_CLSD => Err(Error::ConnectionClosed),
        lwip_sys::ERR_ARG => Err(Error::IllegalArgument),
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum IpAddr {
    Ip4([u8;  4]),
    Ip6([u16; 8]),
    IpAny
}

pub const IP4_ANY: IpAddr = IpAddr::Ip4([0, 0, 0, 0]);
pub const IP6_ANY: IpAddr = IpAddr::Ip6([0, 0, 0, 0, 0, 0, 0, 0]);
pub const IP_ANY: IpAddr = IpAddr::IpAny;

impl IpAddr {
    fn into_raw(self) -> lwip_sys::ip_addr {
        match self {
            IpAddr::Ip4(ref octets) =>
                lwip_sys::ip_addr {
                    data:  [(octets[0] as u32) << 24 |
                            (octets[1] as u32) << 16 |
                            (octets[2] as u32) << 8  |
                            (octets[3] as u32) << 0,
                            0, 0, 0],
                    type_: lwip_sys::IPADDR_TYPE_V4
                },
            IpAddr::Ip6(ref segments) =>
                lwip_sys::ip_addr {
                    data:  [(segments[0] as u32) << 16 | (segments[1] as u32),
                            (segments[2] as u32) << 16 | (segments[3] as u32),
                            (segments[4] as u32) << 16 | (segments[5] as u32),
                            (segments[6] as u32) << 16 | (segments[7] as u32)],
                    type_: lwip_sys::IPADDR_TYPE_V6
                },
            IpAddr::IpAny =>
                lwip_sys::ip_addr {
                    data:  [0; 4],
                    type_: lwip_sys::IPADDR_TYPE_ANY
                }
        }
    }

    unsafe fn from_raw(raw: *mut lwip_sys::ip_addr) -> IpAddr {
        match *raw {
            lwip_sys::ip_addr { type_: lwip_sys::IPADDR_TYPE_V4, data } =>
                IpAddr::Ip4([(data[0] >> 24) as u8,
                             (data[0] >> 16) as u8,
                             (data[0] >>  8) as u8,
                             (data[0] >>  0) as u8]),
            lwip_sys::ip_addr { type_: lwip_sys::IPADDR_TYPE_V6, data } =>
                IpAddr::Ip6([(data[0] >> 16) as u16, data[0] as u16,
                             (data[1] >> 16) as u16, data[1] as u16,
                             (data[2] >> 16) as u16, data[2] as u16,
                             (data[3] >> 16) as u16, data[3] as u16]),
            lwip_sys::ip_addr { type_: lwip_sys::IPADDR_TYPE_ANY, .. } =>
                IpAddr::IpAny
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct SocketAddr {
    pub ip:   IpAddr,
    pub port: u16
}

impl SocketAddr {
    pub fn new(ip: IpAddr, port: u16) -> SocketAddr {
        SocketAddr { ip: ip, port: port }
    }
}

#[derive(Debug)]
pub struct Pbuf<'payload> {
    raw:     *mut lwip_sys::pbuf,
    phantom: PhantomData<&'payload [u8]>
}

#[cfg(not(feature = "preemption"))]
unsafe impl<'payload> Send for Pbuf<'payload> {}

impl<'payload> Pbuf<'payload> {
    unsafe fn from_raw(raw: *mut lwip_sys::pbuf) -> Pbuf<'payload> {
        Pbuf { raw: raw, phantom: PhantomData }
    }

    fn as_raw(&self) -> *mut lwip_sys::pbuf {
        self.raw
    }

    #[allow(dead_code)]
    fn into_raw(self) -> *mut lwip_sys::pbuf {
        let raw = self.raw;
        core::mem::forget(self);
        raw
    }

    fn from_slice_with_type<'a>(slice: &'a [u8], type_: lwip_sys::pbuf_type) -> Pbuf<'a> {
        assert!(slice.len() <= core::u16::MAX as usize);
        unsafe {
            let raw = lwip_sys::pbuf_alloc(lwip_sys::PBUF_RAW, slice.len() as u16, type_);
            (*raw).payload = slice.as_ptr() as *mut u8 as *mut c_void;
            Pbuf { raw: raw, phantom: PhantomData }
        }
    }

    pub fn from_slice(slice: &'payload [u8]) -> Pbuf<'payload> {
        Self::from_slice_with_type(slice, lwip_sys::PBUF_REF)
    }

    pub fn from_static_slice(slice: &'static [u8]) -> Pbuf<'static> {
        // Avoids a copy.
        Self::from_slice_with_type(slice, lwip_sys::PBUF_ROM)
    }

    pub fn len(&self) -> usize {
        unsafe { (*self.raw).len as usize }
    }

    pub fn as_slice(&self) -> &'payload [u8] {
        unsafe {
            core::slice::from_raw_parts((*self.raw).payload as *const u8,
                                        (*self.raw).len as usize)
        }
    }

    pub fn as_mut_slice(&mut self) -> &'payload mut [u8] {
        unsafe {
            core::slice::from_raw_parts_mut((*self.raw).payload as *mut u8,
                                            (*self.raw).len as usize)
        }
    }

    pub fn concat(&mut self, tail: Pbuf<'payload>) {
        unsafe { lwip_sys::pbuf_cat(self.raw, tail.raw) }
    }

    pub fn chain(&mut self, tail: &mut Pbuf<'payload>) {
        unsafe { lwip_sys::pbuf_chain(self.raw, tail.raw) }
    }
}

impl<'a> Drop for Pbuf<'a> {
    fn drop(&mut self) {
        unsafe { lwip_sys::pbuf_free(self.raw) }
    }
}

#[derive(Debug)]
pub struct UdpSocketState {
    recv_buffer: LinkedList<(Pbuf<'static>, SocketAddr)>
}

impl UdpSocketState {
    pub fn readable(&self) -> bool {
        !self.recv_buffer.is_empty()
    }
}

#[derive(Debug)]
pub struct UdpSocket {
    raw:   *mut lwip_sys::udp_pcb,
    state: Box<RefCell<UdpSocketState>>
}

#[cfg(not(feature = "preemption"))]
unsafe impl Send for UdpSocket {}

impl UdpSocket {
    pub fn new() -> Result<UdpSocket> {
        extern fn recv(arg: *mut c_void, _pcb: *mut lwip_sys::udp_pcb,
                       pbuf: *mut lwip_sys::pbuf,
                       addr: *mut lwip_sys::ip_addr, port: u16) {
            unsafe {
                let state = arg as *mut RefCell<UdpSocketState>;
                let socket_addr = SocketAddr { ip: IpAddr::from_raw(addr), port: port };
                (*state).borrow_mut().recv_buffer.push_back((Pbuf::from_raw(pbuf), socket_addr));
            }
        }

        unsafe {
            let raw = lwip_sys::udp_new();
            if raw.is_null() { return Err(Error::OutOfMemory) }

            let mut state = Box::new(RefCell::new(UdpSocketState {
                recv_buffer: LinkedList::new()
            }));
            let arg = &mut *state as *mut RefCell<UdpSocketState> as *mut _;
            lwip_sys::udp_recv(raw, Some(recv), arg);
            Ok(UdpSocket { raw: raw, state: state })
        }
    }

    pub fn state(&self) -> &RefCell<UdpSocketState> {
        &*self.state
    }

    pub fn bind(&self, addr: SocketAddr) -> Result<()> {
        result_from(unsafe {
            lwip_sys::udp_bind(self.raw, &mut addr.ip.into_raw(), addr.port)
        }, || ())
    }

    pub fn connect(&self, addr: SocketAddr) -> Result<()> {
        result_from(unsafe {
            lwip_sys::udp_connect(self.raw, &mut addr.ip.into_raw(), addr.port)
        }, || ())
    }

    pub fn disconnect(&self) -> Result<()> {
        result_from(unsafe {
            lwip_sys::udp_disconnect(self.raw)
        }, || ())
    }

    pub fn send<'a>(&'a self, pbuf: Pbuf<'a>) -> Result<()> {
        result_from(unsafe {
            lwip_sys::udp_send(self.raw, pbuf.as_raw())
        }, || ())
    }

    pub fn send_to<'a>(&'a self, pbuf: Pbuf<'a>, addr: SocketAddr) -> Result<()> {
        result_from(unsafe {
            lwip_sys::udp_sendto(self.raw, pbuf.as_raw(),
                                 &mut addr.ip.into_raw(), addr.port)
        }, || ())
    }

    pub fn try_recv(&self) -> Option<(Pbuf<'static>, SocketAddr)> {
        self.state.borrow_mut().recv_buffer.pop_front()
    }
}

impl Drop for UdpSocket {
    fn drop(&mut self) {
        unsafe { lwip_sys::udp_remove(self.raw) }
    }
}

#[derive(Debug)]
pub struct TcpListenerState {
    backlog: LinkedList<TcpStream>
}

impl TcpListenerState {
    pub fn acceptable(&self) -> bool {
        !self.backlog.is_empty()
    }
}

#[derive(Debug)]
pub struct TcpListener {
    raw:   *mut lwip_sys::tcp_pcb,
    state: Box<RefCell<TcpListenerState>>
}

#[cfg(not(feature = "preemption"))]
unsafe impl Send for TcpListener {}

impl TcpListener {
    pub fn bind(addr: SocketAddr) -> Result<TcpListener> {
        extern fn accept(arg: *mut c_void, newpcb: *mut lwip_sys::tcp_pcb,
                         err: lwip_sys::err) -> lwip_sys::err {
            if err != lwip_sys::ERR_OK { return err }
            unsafe {
                let state = arg as *mut RefCell<TcpListenerState>;
                (*state).borrow_mut().backlog.push_back(TcpStream::from_raw(newpcb));
            }
            lwip_sys::ERR_OK
        }

        unsafe {
            let raw = lwip_sys::tcp_new();
            if raw.is_null() { return Err(Error::OutOfMemory) }
            try!(result_from(lwip_sys::tcp_bind(raw, &mut addr.ip.into_raw(), addr.port),
                             || ()));

            let raw2 = lwip_sys::tcp_listen_with_backlog(raw, 0xff);
            if raw2.is_null() {
                lwip_sys::tcp_abort(raw);
                return Err(Error::OutOfMemory)
            }

            let mut state = Box::new(RefCell::new(TcpListenerState {
                backlog: LinkedList::new()
            }));
            let arg = &mut *state as *mut RefCell<TcpListenerState> as *mut _;
            lwip_sys::tcp_arg(raw2, arg);
            lwip_sys::tcp_accept(raw2, Some(accept));
            Ok(TcpListener { raw: raw2, state: state })
        }
    }

    pub fn state(&self) -> &RefCell<TcpListenerState> {
        &*self.state
    }

    pub fn try_accept(&self) -> Option<TcpStream> {
        self.state.borrow_mut().backlog.pop_front()
    }

    pub fn keepalive(&self) -> bool {
        unsafe { *lwip_sys::tcp_so_options_(self.raw) & lwip_sys::SOF_KEEPALIVE != 0 }
    }

    pub fn set_keepalive(&self, keepalive: bool) {
        if keepalive {
            unsafe { *lwip_sys::tcp_so_options_(self.raw) |= lwip_sys::SOF_KEEPALIVE }
        } else {
            unsafe { *lwip_sys::tcp_so_options_(self.raw) &= !lwip_sys::SOF_KEEPALIVE }
        }
    }
}

impl Drop for TcpListener {
    fn drop(&mut self) {
        unsafe {
            // tcp_close never fails on listening sockets
            let _ = lwip_sys::tcp_close(self.raw);
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Shutdown {
    Read,
    Write,
    Both,
}

#[derive(Debug)]
pub struct TcpStreamState {
    recv_buffer: LinkedList<Result<Pbuf<'static>>>,
    send_avail:  usize
}

impl TcpStreamState {
    pub fn readable(&self) -> bool {
        !self.recv_buffer.is_empty()
    }

    pub fn writeable(&self) -> bool {
        !(self.send_avail == 0)
    }
}

#[derive(Debug)]
pub struct TcpStream {
    raw:   *mut lwip_sys::tcp_pcb,
    state: Box<RefCell<TcpStreamState>>
}

#[cfg(not(feature = "preemption"))]
unsafe impl Send for TcpStream {}

impl TcpStream {
    fn from_raw(raw: *mut lwip_sys::tcp_pcb) -> TcpStream {
        extern fn recv(arg: *mut c_void, _raw: *mut lwip_sys::tcp_pcb,
                       pbuf: *mut lwip_sys::pbuf, err: lwip_sys::err) -> lwip_sys::err {
            if err != lwip_sys::ERR_OK { return err }
            unsafe {
                let state = arg as *mut RefCell<TcpStreamState>;
                if pbuf.is_null() {
                    (*state).borrow_mut().recv_buffer.push_back(Err(Error::ConnectionClosed))
                } else {
                    (*state).borrow_mut().recv_buffer.push_back(Ok(Pbuf::from_raw(pbuf)))
                }
            }
            lwip_sys::ERR_OK
        }

        extern fn sent(arg: *mut c_void, raw: *mut lwip_sys::tcp_pcb,
                       _len: u16) -> lwip_sys::err {
            unsafe {
                let state = arg as *mut RefCell<TcpStreamState>;
                (*state).borrow_mut().send_avail = lwip_sys::tcp_sndbuf_(raw) as usize;
            }
            lwip_sys::ERR_OK
        }

        extern fn err(arg: *mut c_void, err: lwip_sys::err) {
            unsafe {
                let state = arg as *mut RefCell<TcpStreamState>;
                (*state).borrow_mut().recv_buffer.push_back(result_from(err, || unreachable!()))
            }
        }

        unsafe {
            let mut state = Box::new(RefCell::new(TcpStreamState {
                recv_buffer: LinkedList::new(),
                send_avail:  lwip_sys::tcp_sndbuf_(raw) as usize
            }));
            let arg = &mut *state as *mut RefCell<TcpStreamState> as *mut _;
            lwip_sys::tcp_arg(raw, arg);
            lwip_sys::tcp_recv(raw, Some(recv));
            lwip_sys::tcp_sent(raw, Some(sent));
            lwip_sys::tcp_err(raw, Some(err));
            TcpStream { raw: raw, state: state }
        }
    }

    pub fn state(&self) -> &RefCell<TcpStreamState> {
        &*self.state
    }

    pub fn write(&self, data: &[u8]) -> Result<usize> {
        let sndbuf = unsafe { lwip_sys::tcp_sndbuf_(self.raw) } as usize;
        let len = if data.len() < sndbuf { data.len() } else { sndbuf };
        let result = result_from(unsafe {
            lwip_sys::tcp_write(self.raw, data as *const [u8] as *const _, len as u16,
                                lwip_sys::TCP_WRITE_FLAG_COPY |
                                lwip_sys::TCP_WRITE_FLAG_MORE)
        }, || len);
        self.state.borrow_mut().send_avail = unsafe { lwip_sys::tcp_sndbuf_(self.raw) } as usize;
        result
    }

    pub fn flush(&self) -> Result<()> {
        const EMPTY_DATA: [u8; 0] = [];
        result_from(unsafe {
            lwip_sys::tcp_write(self.raw, &EMPTY_DATA as *const [u8] as *const _, 0, 0)
        }, || ())
    }

    pub fn try_read(&self) -> Result<Option<Pbuf<'static>>> {
        let mut state = self.state.borrow_mut();
        match state.recv_buffer.front() {
            None => return Ok(None),
            Some(&Err(err)) => return Err(err),
            Some(_) => ()
        }
        match state.recv_buffer.pop_front() {
            Some(Ok(pbuf)) => {
                unsafe { lwip_sys::tcp_recved(self.raw, pbuf.len() as u16) }
                return Ok(Some(pbuf))
            },
            _ => unreachable!()
        }
    }

    pub fn shutdown(&self, how: Shutdown) -> Result<()> {
        let (shut_rx, shut_tx) = match how {
            Shutdown::Read  => (1, 0),
            Shutdown::Write => (0, 1),
            Shutdown::Both  => (1, 1)
        };
        result_from(unsafe {
            lwip_sys::tcp_shutdown(self.raw, shut_rx, shut_tx)
        }, || ())
    }

    pub fn close(self) -> Result<()> {
        let result = result_from(unsafe {
            lwip_sys::tcp_close(self.raw)
        }, || ());
        core::mem::forget(self); // closing twice is illegal
        result
    }
}

impl Drop for TcpStream {
    fn drop(&mut self) {
        unsafe {
            // lwip *will* try to call back after tcp_close
            lwip_sys::tcp_recv(self.raw, None);
            lwip_sys::tcp_sent(self.raw, None);
            lwip_sys::tcp_err(self.raw, None);

            // tcp_close can fail here, but in drop() we don't care
            let _ = lwip_sys::tcp_close(self.raw);
        }
    }
}
