#![no_std]
#![feature(libc)]
#![allow(non_camel_case_types)]

extern crate libc;

pub use err::*;
pub use pbuf_layer::*;
pub use pbuf_type::*;
pub use ip_addr_type::*;

use libc::{c_void, c_int};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(i8)]
pub enum err {
    ERR_OK         =  0,
    ERR_MEM        = -1,
    ERR_BUF        = -2,
    ERR_TIMEOUT    = -3,
    ERR_RTE        = -4,
    ERR_INPROGRESS = -5,
    ERR_VAL        = -6,
    ERR_WOULDBLOCK = -7,
    ERR_USE        = -8,
    ERR_ALREADY    = -9,
    ERR_ISCONN     = -10,
    ERR_CONN       = -11,
    ERR_IF         = -12,
    ERR_ABRT       = -13,
    ERR_RST        = -14,
    ERR_CLSD       = -15,
    ERR_ARG        = -16,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum pbuf_layer {
    PBUF_TRANSPORT,
    PBUF_IP,
    PBUF_LINK,
    PBUF_RAW_TX,
    PBUF_RAW
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum pbuf_type {
    PBUF_RAM,
    PBUF_ROM,
    PBUF_REF,
    PBUF_POOL,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum ip_addr_type {
    IPADDR_TYPE_V4  = 0,
    IPADDR_TYPE_V6  = 6,
    IPADDR_TYPE_ANY = 46,
}

#[repr(C)]
pub struct pbuf {
    pub next:    *mut pbuf,
    pub payload: *mut c_void,
    pub tot_len: u16,
    pub len:     u16,
    pub type_:   pbuf_type,
    pub flags:   u8,
    pub ref_:    u16
}

#[derive(Clone)]
#[repr(C)]
pub struct ip4_addr {
    pub addr: u32
}

#[derive(Clone)]
#[repr(C)]
pub struct ip6_addr {
    pub addr: [u32; 4]
}

#[derive(Clone)]
#[repr(C)]
pub struct ip_addr {
    pub data:  [u32; 4],
    pub type_: ip_addr_type
}

#[repr(C)]
pub struct tcp_pcb {
    __opaque: c_void
}

#[repr(C)]
pub struct udp_pcb {
    __opaque: c_void
}

pub const TCP_WRITE_FLAG_COPY: u8 = 0x01;
pub const TCP_WRITE_FLAG_MORE: u8 = 0x02;

extern {
    pub fn pbuf_alloc(l: pbuf_layer, length: u16, type_: pbuf_type) -> *mut pbuf;
    pub fn pbuf_realloc(p: *mut pbuf, length: u16);
    pub fn pbuf_ref(p: *mut pbuf);
    pub fn pbuf_free(p: *mut pbuf);
    pub fn pbuf_cat(head: *mut pbuf, tail: *mut pbuf);
    pub fn pbuf_chain(head: *mut pbuf, tail: *mut pbuf);
    pub fn pbuf_dechain(p: *mut pbuf) -> *mut pbuf;
    pub fn pbuf_copy(p_to: *mut pbuf, p_from: *mut pbuf) -> err;
    pub fn pbuf_copy_partial(p: *mut pbuf, dataptr: *mut c_void, len: u16, offset: u16) -> u16;
    pub fn pbuf_take(p: *mut pbuf, dataptr: *const c_void, len: u16) -> err;
    pub fn pbuf_take_at(p: *mut pbuf, dataptr: *const c_void, len: u16, offset: u16) -> err;
    pub fn pbuf_skip(in_: *mut pbuf, in_offset: u16, out_offset: *mut u16) -> *mut pbuf;

    pub fn tcp_new() -> *mut tcp_pcb;
    pub fn tcp_arg(pcb: *mut tcp_pcb, arg: *mut c_void);
    pub fn tcp_bind(pcb: *mut tcp_pcb, ipaddr: *mut ip_addr, port: u16) -> err;
    pub fn tcp_listen_with_backlog(pcb: *mut tcp_pcb, backlog: u8) -> *mut tcp_pcb;
    pub fn tcp_accept(pcb: *mut tcp_pcb,
                      accept: extern fn(arg: *mut c_void, newpcb: *mut tcp_pcb,
                                        err: err) -> err);
    pub fn tcp_connect(pcb: *mut tcp_pcb, ipaddr: *mut ip_addr, port: u16,
                       connected: extern fn(arg: *mut c_void, tcb: *mut tcp_pcb, err: err)) -> err;
    pub fn tcp_write(pcb: *mut tcp_pcb, dataptr: *const c_void, len: u16, apiflags: u8) -> err;
    pub fn tcp_sent(pcb: *mut tcp_pcb,
                    sent: extern fn(arg: *mut c_void, tcb: *mut tcp_pcb, len: u16) -> err);
    pub fn tcp_recv(pcb: *mut tcp_pcb,
                    recv: extern fn(arg: *mut c_void, tcb: *mut tcp_pcb, p: *mut pbuf,
                                    err: err) -> err);
    pub fn tcp_recved(pcb: *mut tcp_pcb, len: u16);
    pub fn tcp_poll(pcb: *mut tcp_pcb,
                    poll: extern fn(arg: *mut c_void, tcb: *mut tcp_pcb),
                    interval: u8);
    pub fn tcp_shutdown(pcb: *mut tcp_pcb, shut_rx: c_int, shut_tx: c_int) -> err;
    pub fn tcp_close(pcb: *mut tcp_pcb) -> err;
    pub fn tcp_abort(pcb: *mut tcp_pcb);
    pub fn tcp_err(pcb: *mut tcp_pcb,
                   err: extern fn(arg: *mut c_void, err: err));

    // nonstandard
    pub fn tcp_sndbuf_(pcb: *mut tcp_pcb) -> u16;

    pub fn udp_new() -> *mut udp_pcb;
    pub fn udp_new_ip_type(type_: ip_addr_type) -> *mut udp_pcb;
    pub fn udp_remove(pcb: *mut udp_pcb);
    pub fn udp_bind(pcb: *mut udp_pcb, ipaddr: *mut ip_addr, port: u16) -> err;
    pub fn udp_connect(pcb: *mut udp_pcb, ipaddr: *mut ip_addr, port: u16) -> err;
    pub fn udp_disconnect(pcb: *mut udp_pcb) -> err;
    pub fn udp_send(pcb: *mut udp_pcb, p: *mut pbuf) -> err;
    pub fn udp_sendto(pcb: *mut udp_pcb, p: *mut pbuf, ipaddr: *mut ip_addr, port: u16) -> err;
    pub fn udp_recv(pcb: *mut udp_pcb,
                    recv: extern fn(arg: *mut c_void, upcb: *mut udp_pcb, p: *mut pbuf,
                                    addr: *mut ip_addr, port: u16),
                    recv_arg: *mut c_void);
}
