use core::fmt;
use dyld;

pub const KERNELCPU_EXEC_ADDRESS:    usize = 0x40800000;
pub const KERNELCPU_PAYLOAD_ADDRESS: usize = 0x40840000;
pub const KERNELCPU_LAST_ADDRESS:    usize = 0x4fffffff;
pub const KSUPPORT_HEADER_SIZE:      usize = 0x80;

#[derive(Debug, Clone)]
pub struct Exception<'a> {
    pub name:     &'a str,
    pub file:     &'a str,
    pub line:     u32,
    pub column:   u32,
    pub function: &'a str,
    pub message:  &'a str,
    pub param:    [i64; 3]
}

#[derive(Debug)]
pub enum Message<'a> {
    LoadRequest(&'a [u8]),
    LoadReply(Result<(), dyld::Error<'a>>),

    NowInitRequest,
    NowInitReply(u64),
    NowSave(u64),

    RtioInitRequest,

    DmaRecordStart(&'a str),
    DmaRecordAppend(&'a [u8]),
    DmaRecordStop {
        duration:  u64
    },

    DmaEraseRequest {
        name: &'a str
    },

    DmaRetrieveRequest {
        name: &'a str
    },
    DmaRetrieveReply {
        trace:    Option<&'a [u8]>,
        duration: u64
    },

    DrtioChannelStateRequest { channel: u32 },
    DrtioChannelStateReply { fifo_space: u16, last_timestamp: u64 },
    DrtioResetChannelStateRequest { channel: u32 },
    DrtioGetFifoSpaceRequest { channel: u32 },
    DrtioPacketCountRequest { linkno: u8 },
    DrtioPacketCountReply { tx_cnt: u32, rx_cnt: u32 },
    DrtioFifoSpaceReqCountRequest { linkno: u8 },
    DrtioFifoSpaceReqCountReply { cnt: u32 },

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

    I2cStartRequest { busno: u32 },
    I2cRestartRequest { busno: u32 },
    I2cStopRequest { busno: u32 },
    I2cWriteRequest { busno: u32, data: u8 },
    I2cWriteReply { succeeded: bool, ack: bool },
    I2cReadRequest { busno: u32, ack: bool },
    I2cReadReply { succeeded: bool, data: u8 },
    I2cBasicReply { succeeded: bool },

    SpiSetConfigRequest { busno: u32, flags: u8, write_div: u8, read_div: u8 },
    SpiSetXferRequest { busno: u32, chip_select: u16, write_length: u8, read_length: u8 },
    SpiWriteRequest { busno: u32, data: u32 },
    SpiReadRequest { busno: u32 },
    SpiReadReply { succeeded: bool, data: u32 },
    SpiBasicReply { succeeded: bool },

    Log(fmt::Arguments<'a>),
    LogSlice(&'a str)
}

pub use self::Message::*;
