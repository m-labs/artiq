use core::fmt;
use cslice::CSlice;
use dyld;

pub const KERNELCPU_EXEC_ADDRESS:    usize = 0x45000000;
pub const KERNELCPU_PAYLOAD_ADDRESS: usize = 0x45060000;
pub const KERNELCPU_LAST_ADDRESS:    usize = 0x4fffffff;
pub const KSUPPORT_HEADER_SIZE:      usize = 0x80;

#[derive(Debug)]
pub enum Message<'a> {
    LoadRequest(&'a [u8]),
    LoadReply(Result<(), dyld::Error<'a>>),

    RtioInitRequest,

    RtioDestinationStatusRequest { destination: u8 },
    RtioDestinationStatusReply { up: bool },

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

    RunFinished,
    RunException {
        exceptions: &'a [Option<eh::eh_artiq::Exception<'a>>],
        stack_pointers: &'a [eh::eh_artiq::StackPointerBacktrace],
        backtrace: &'a [(usize, usize)]
    },
    RunAborted,

    RpcSend {
        async: bool,
        service: u32,
        tag: &'a [u8],
        data: *const *const ()
    },
    RpcRecvRequest(*mut ()),
    RpcRecvReply(Result<usize, eh::eh_artiq::Exception<'a>>),
    RpcFlush,

    CacheGetRequest { key: &'a str },
    CacheGetReply   { value: *const CSlice<'static, i32> },
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
    I2cSwitchSelectRequest { busno: u32, address: u8, mask: u8 },

    SpiSetConfigRequest { busno: u32, flags: u8, length: u8, div: u8, cs: u8 },
    SpiWriteRequest { busno: u32, data: u32 },
    SpiReadRequest { busno: u32 },
    SpiReadReply { succeeded: bool, data: u32 },
    SpiBasicReply { succeeded: bool },

    Log(fmt::Arguments<'a>),
    LogSlice(&'a str)
}

pub use self::Message::*;
