#![allow(dead_code)]

use core::marker::PhantomData;
use core::fmt;

pub const KERNELCPU_EXEC_ADDRESS:    usize = 0x40800000;
pub const KERNELCPU_PAYLOAD_ADDRESS: usize = 0x40840000;
pub const KERNELCPU_LAST_ADDRESS:    usize = 0x4fffffff;
pub const KSUPPORT_HEADER_SIZE:      usize = 0x80;

#[repr(C)]
#[derive(Debug, Clone)]
pub struct Exception<'a> {
    pub name:     *const u8,
    pub file:     *const u8,
    pub line:     u32,
    pub column:   u32,
    pub function: *const u8,
    pub message:  *const u8,
    pub param:    [i64; 3],
    pub phantom:  PhantomData<&'a str>
}

#[derive(Debug)]
pub enum Message<'a> {
    LoadRequest(&'a [u8]),
    LoadReply(Result<(), &'a str>),

    NowInitRequest,
    NowInitReply(u64),
    NowSave(u64),

    RTIOInitRequest,

    DRTIOChannelStateRequest { channel: u32 },
    DRTIOChannelStateReply { fifo_space: u16, last_timestamp: u64 },
    DRTIOResetChannelStateRequest { channel: u32 },
    DRTIOGetFIFOSpaceRequest { channel: u32 },
    DRTIOPacketCountRequest,
    DRTIOPacketCountReply { tx_cnt: u32, rx_cnt: u32 },

    RunFinished,
    RunException {
        exception: Exception<'a>,
        backtrace: &'a [usize]
    },
    RunAborted,

    WatchdogSetRequest { ms: u64 },
    WatchdogSetReply   { id: usize },
    WatchdogClear      { id: usize },

    RpcSend {
        async: bool,
        service: u32,
        tag: &'a [u8],
        data: *const *const ()
    },
    RpcRecvRequest(*mut ()),
    RpcRecvReply(Result<usize, Exception<'a>>),

    CacheGetRequest { key: &'a str },
    CacheGetReply   { value: &'static [i32] },
    CachePutRequest { key: &'a str, value: &'a [i32] },
    CachePutReply   { succeeded: bool },

    I2CStartRequest { busno: u8 },
    I2CStopRequest { busno: u8 },
    I2CWriteRequest { busno: u8, data: u8 },
    I2CWriteReply { ack: bool },
    I2CReadRequest { busno: u8, ack: bool },
    I2CReadReply { data: u8 },

    Log(fmt::Arguments<'a>),
    LogSlice(&'a str)
}

pub use self::Message::*;
