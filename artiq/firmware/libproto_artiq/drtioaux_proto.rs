use io::{Read, ProtoRead, Write, ProtoWrite, Error as IoError};

#[derive(Fail, Debug)]
pub enum Error<T> {
    #[fail(display = "unknown packet {:#02x}", _0)]
    UnknownPacket(u8),
    #[fail(display = "{}", _0)]
    Io(#[cause] IoError<T>)
}

impl<T> From<IoError<T>> for Error<T> {
    fn from(value: IoError<T>) -> Error<T> {
        Error::Io(value)
    }
}

// maximum size of arbitrary payloads
// used by satellite -> master analyzer, subkernel exceptions
pub const SAT_PAYLOAD_MAX_SIZE: usize  = /*max size*/512 - /*header*/3 - /*CRC*/4 - /*packet ID*/1 - /*last*/1 - /*length*/2;
// used by DDMA, subkernel program data (need to provide extra ID and destination)
pub const MASTER_PAYLOAD_MAX_SIZE: usize = SAT_PAYLOAD_MAX_SIZE - /*ID*/4;

#[derive(PartialEq, Clone, Copy, Debug)]
#[repr(u8)]
pub enum PayloadStatus {
    Middle = 0,
    First = 1,
    Last = 2,
    FirstAndLast = 3,
}

impl From<u8> for PayloadStatus {
    fn from(value: u8) -> PayloadStatus {
        match value {
            0 => PayloadStatus::Middle,
            1 => PayloadStatus::First,
            2 => PayloadStatus::Last,
            3 => PayloadStatus::FirstAndLast,
            _ => unreachable!(),
        }
    }
}

impl PayloadStatus {
    pub fn is_first(self) -> bool {
        self == PayloadStatus::First || self == PayloadStatus::FirstAndLast
    }

    pub fn is_last(self) -> bool {
        self == PayloadStatus::Last || self == PayloadStatus::FirstAndLast
    }

    pub fn from_status(first: bool, last: bool) -> PayloadStatus {
        match (first, last) {
            (true, true) => PayloadStatus::FirstAndLast,
            (true, false) => PayloadStatus::First,
            (false, true) => PayloadStatus::Last,
            (false, false) => PayloadStatus::Middle
        }
    }
}

#[derive(PartialEq, Clone, Copy, Debug)]
pub struct Packet {
    // header
    pub source: u8,
    pub destination: u8,
    pub transaction_id: u8,
    // actual content below
    pub payload: Payload
}

impl Packet {
    pub fn read_from<R>(reader: &mut R) -> Result<Self, Error<R::ReadError>>
    where R: Read + ?Sized {
        Ok(Packet {
            source: reader.read_u8()?,
            destination: reader.read_u8()?,
            transaction_id: reader.read_u8()?,
            payload: Payload::read_from(reader)?
        })
    }

    pub fn write_to<W>(&self, writer: &mut W) -> Result<(), IoError<W::WriteError>>
    where W: Write + ?Sized {
        writer.write_u8(self.source)?;
        writer.write_u8(self.destination)?;
        writer.write_u8(self.transaction_id)?;
        self.payload.write_to(writer)
    }
}

#[derive(PartialEq, Clone, Copy, Debug)]
pub enum Payload {
    EchoRequest,
    EchoReply,
    ResetRequest,
    ResetAck,
    TSCAck,
    PacketAck,

    DestinationStatusRequest,
    DestinationDownReply,
    DestinationOkReply,
    DestinationSequenceErrorReply { channel: u16 },
    DestinationCollisionReply { channel: u16 },
    DestinationBusyReply { channel: u16 },

    RoutingSetPath { destination: u8, hops: [u8; 32] },
    RoutingSetRank { rank: u8 },
    RoutingRetrievePackets,
    RoutingNoPackets,
    RoutingAck,

    MonitorRequest { channel: u16, probe: u8 },
    MonitorReply { value: u64 },
    InjectionRequest { channel: u16, overrd: u8, value: u8 },
    InjectionStatusRequest { channel: u16, overrd: u8 },
    InjectionStatusReply { value: u8 },

    I2cStartRequest { busno: u8 },
    I2cRestartRequest { busno: u8 },
    I2cStopRequest { busno: u8 },
    I2cWriteRequest { busno: u8, data: u8 },
    I2cWriteReply { succeeded: bool, ack: bool },
    I2cReadRequest { busno: u8, ack: bool },
    I2cReadReply { succeeded: bool, data: u8 },
    I2cBasicReply { succeeded: bool },
    I2cSwitchSelectRequest { busno: u8, address: u8, mask: u8 },

    SpiSetConfigRequest { busno: u8, flags: u8, length: u8, div: u8, cs: u8 },
    SpiWriteRequest { busno: u8, data: u32 },
    SpiReadRequest { busno: u8 },
    SpiReadReply { succeeded: bool, data: u32 },
    SpiBasicReply { succeeded: bool },

    AnalyzerHeaderRequest,
    AnalyzerHeader { sent_bytes: u32, total_byte_count: u64, overflow_occurred: bool },
    AnalyzerDataRequest,
    AnalyzerData { last: bool, length: u16, data: [u8; SAT_PAYLOAD_MAX_SIZE]},

    DmaAddTraceRequest { 
        id: u32, status: PayloadStatus,
        length: u16, trace: [u8; MASTER_PAYLOAD_MAX_SIZE] 
    },
    DmaAddTraceReply { id: u32, succeeded: bool },
    DmaRemoveTraceRequest { id: u32 },
    DmaRemoveTraceReply { succeeded: bool },
    DmaPlaybackRequest { id: u32, timestamp: u64 },
    DmaPlaybackReply { succeeded: bool },
    DmaPlaybackStatus { id: u32, error: u8, channel: u32, timestamp: u64 },

    SubkernelAddDataRequest { id: u32, status: PayloadStatus, length: u16, data: [u8; MASTER_PAYLOAD_MAX_SIZE] },
    SubkernelAddDataReply { succeeded: bool },
    SubkernelLoadRunRequest { id: u32, run: bool },
    SubkernelLoadRunReply { succeeded: bool },
    SubkernelFinished { id: u32, with_exception: bool, exception_src: u8 },
    SubkernelExceptionRequest,
    SubkernelException { last: bool, length: u16, data: [u8; SAT_PAYLOAD_MAX_SIZE] },
    SubkernelMessage { id: u32, status: PayloadStatus, length: u16, data: [u8; MASTER_PAYLOAD_MAX_SIZE] },
    SubkernelMessageAck,
}

impl Payload {
    pub fn read_from<R>(reader: &mut R) -> Result<Self, Error<R::ReadError>>
        where R: Read + ?Sized
    {
        Ok(match reader.read_u8()? {
            0x00 => Payload::EchoRequest,
            0x01 => Payload::EchoReply,
            0x02 => Payload::ResetRequest,
            0x03 => Payload::ResetAck,
            0x04 => Payload::TSCAck,
            0x05 => Payload::PacketAck,

            0x20 => Payload::DestinationStatusRequest,
            0x21 => Payload::DestinationDownReply,
            0x22 => Payload::DestinationOkReply,
            0x23 => Payload::DestinationSequenceErrorReply {
                channel: reader.read_u16()?
            },
            0x24 => Payload::DestinationCollisionReply {
                channel: reader.read_u16()?
            },
            0x25 => Payload::DestinationBusyReply {
                channel: reader.read_u16()?
            },

            0x30 => {
                let destination = reader.read_u8()?;
                let mut hops = [0; 32];
                reader.read_exact(&mut hops)?;
                Payload::RoutingSetPath {
                    destination: destination,
                    hops: hops
                }
            },
            0x31 => Payload::RoutingSetRank {
                rank: reader.read_u8()?
            },
            0x32 => Payload::RoutingAck,
            0x33 => Payload::RoutingRetrievePackets,
            0x34 => Payload::RoutingNoPackets,

            0x40 => Payload::MonitorRequest {
                channel: reader.read_u16()?,
                probe: reader.read_u8()?
            },
            0x41 => Payload::MonitorReply {
                value: reader.read_u64()?
            },
            0x50 => Payload::InjectionRequest {
                channel: reader.read_u16()?,
                overrd: reader.read_u8()?,
                value: reader.read_u8()?
            },
            0x51 => Payload::InjectionStatusRequest {
                channel: reader.read_u16()?,
                overrd: reader.read_u8()?
            },
            0x52 => Payload::InjectionStatusReply {
                value: reader.read_u8()?
            },

            0x80 => Payload::I2cStartRequest {
                busno: reader.read_u8()?
            },
            0x81 => Payload::I2cRestartRequest {
                busno: reader.read_u8()?
            },
            0x82 => Payload::I2cStopRequest {
                busno: reader.read_u8()?
            },
            0x83 => Payload::I2cWriteRequest {
                busno: reader.read_u8()?,
                data: reader.read_u8()?
            },
            0x84 => Payload::I2cWriteReply {
                succeeded: reader.read_bool()?,
                ack: reader.read_bool()?
            },
            0x85 => Payload::I2cReadRequest {
                busno: reader.read_u8()?,
                ack: reader.read_bool()?
            },
            0x86 => Payload::I2cReadReply {
                succeeded: reader.read_bool()?,
                data: reader.read_u8()?
            },
            0x87 => Payload::I2cBasicReply {
                succeeded: reader.read_bool()?
            },
            0x88 => Payload::I2cSwitchSelectRequest {
                busno: reader.read_u8()?,
                address: reader.read_u8()?,
                mask: reader.read_u8()?,
            },

            0x90 => Payload::SpiSetConfigRequest {
                busno: reader.read_u8()?,
                flags: reader.read_u8()?,
                length: reader.read_u8()?,
                div: reader.read_u8()?,
                cs: reader.read_u8()?
            },
            /* 0x91: was Payload::SpiSetXferRequest */
            0x92 => Payload::SpiWriteRequest {
                busno: reader.read_u8()?,
                data: reader.read_u32()?
            },
            0x93 => Payload::SpiReadRequest {
                busno: reader.read_u8()?
            },
            0x94 => Payload::SpiReadReply {
                succeeded: reader.read_bool()?,
                data: reader.read_u32()?
            },
            0x95 => Payload::SpiBasicReply {
                succeeded: reader.read_bool()?
            },

            0xa0 => Payload::AnalyzerHeaderRequest,
            0xa1 => Payload::AnalyzerHeader {
                sent_bytes: reader.read_u32()?, 
                total_byte_count: reader.read_u64()?, 
                overflow_occurred: reader.read_bool()?,
            },
            0xa2 => Payload::AnalyzerDataRequest,
            0xa3 => {
                let last = reader.read_bool()?;
                let length = reader.read_u16()?;
                let mut data: [u8; SAT_PAYLOAD_MAX_SIZE] = [0; SAT_PAYLOAD_MAX_SIZE];
                reader.read_exact(&mut data[0..length as usize])?;
                Payload::AnalyzerData {
                    last: last,
                    length: length,
                    data: data
                }
            },

            0xb0 => {
                let id = reader.read_u32()?;
                let status = reader.read_u8()?;
                let length = reader.read_u16()?;
                let mut trace: [u8; MASTER_PAYLOAD_MAX_SIZE] = [0; MASTER_PAYLOAD_MAX_SIZE];
                reader.read_exact(&mut trace[0..length as usize])?;
                Payload::DmaAddTraceRequest {
                    id: id,
                    status: PayloadStatus::from(status),
                    length: length as u16,
                    trace: trace,
                }
            },
            0xb1 => Payload::DmaAddTraceReply {
                id: reader.read_u32()?,
                succeeded: reader.read_bool()?
            },
            0xb2 => Payload::DmaRemoveTraceRequest {
                id: reader.read_u32()?
            },
            0xb3 => Payload::DmaRemoveTraceReply {
                succeeded: reader.read_bool()?
            },
            0xb4 => Payload::DmaPlaybackRequest {
                id: reader.read_u32()?,
                timestamp: reader.read_u64()?
            },
            0xb5 => Payload::DmaPlaybackReply {
                succeeded: reader.read_bool()?
            },
            0xb6 => Payload::DmaPlaybackStatus {
                id: reader.read_u32()?,
                error: reader.read_u8()?,
                channel: reader.read_u32()?,
                timestamp: reader.read_u64()?
            },

            0xc0 => {
                let id = reader.read_u32()?;
                let status = reader.read_u8()?;
                let length = reader.read_u16()?;
                let mut data: [u8; MASTER_PAYLOAD_MAX_SIZE] = [0; MASTER_PAYLOAD_MAX_SIZE];
                reader.read_exact(&mut data[0..length as usize])?;
                Payload::SubkernelAddDataRequest {
                    id: id,
                    status: PayloadStatus::from(status),
                    length: length as u16,
                    data: data,
                }
            },
            0xc1 => Payload::SubkernelAddDataReply {
                succeeded: reader.read_bool()?
            },
            0xc4 => Payload::SubkernelLoadRunRequest {
                id: reader.read_u32()?,
                run: reader.read_bool()?
            },
            0xc5 => Payload::SubkernelLoadRunReply {
                succeeded: reader.read_bool()?
            },
            0xc8 => Payload::SubkernelFinished {
                id: reader.read_u32()?,
                with_exception: reader.read_bool()?,
                exception_src: reader.read_u8()?
            },
            0xc9 => Payload::SubkernelExceptionRequest,
            0xca => {
                let last = reader.read_bool()?;
                let length = reader.read_u16()?;
                let mut data: [u8; SAT_PAYLOAD_MAX_SIZE] = [0; SAT_PAYLOAD_MAX_SIZE];
                reader.read_exact(&mut data[0..length as usize])?;
                Payload::SubkernelException {
                    last: last,
                    length: length,
                    data: data
                }
            },
            0xcb => {
                let id = reader.read_u32()?;
                let status = reader.read_u8()?;
                let length = reader.read_u16()?;
                let mut data: [u8; MASTER_PAYLOAD_MAX_SIZE] = [0; MASTER_PAYLOAD_MAX_SIZE];
                reader.read_exact(&mut data[0..length as usize])?;
                Payload::SubkernelMessage {
                    id: id,
                    status: PayloadStatus::from(status),
                    length: length as u16,
                    data: data,
                }
            },
            0xcc => Payload::SubkernelMessageAck,

            ty => return Err(Error::UnknownPacket(ty))
        })
    }

    pub fn write_to<W>(&self, writer: &mut W) -> Result<(), IoError<W::WriteError>>
        where W: Write + ?Sized
    {
        match *self {
            Payload::EchoRequest =>
                writer.write_u8(0x00)?,
            Payload::EchoReply =>
                writer.write_u8(0x01)?,
            Payload::ResetRequest =>
                writer.write_u8(0x02)?,
            Payload::ResetAck =>
                writer.write_u8(0x03)?,
            Payload::TSCAck =>
                writer.write_u8(0x04)?,
            Payload::PacketAck =>
                writer.write_u8(0x05)?,

            Payload::DestinationStatusRequest => 
                writer.write_u8(0x20)?,
            Payload::DestinationDownReply =>
                writer.write_u8(0x21)?,
            Payload::DestinationOkReply =>
                writer.write_u8(0x22)?,
            Payload::DestinationSequenceErrorReply { channel } => {
                writer.write_u8(0x23)?;
                writer.write_u16(channel)?;
            },
            Payload::DestinationCollisionReply { channel } => {
                writer.write_u8(0x24)?;
                writer.write_u16(channel)?;
            },
            Payload::DestinationBusyReply { channel } => {
                writer.write_u8(0x25)?;
                writer.write_u16(channel)?;
            },

            Payload::RoutingSetPath { destination, hops } => {
                writer.write_u8(0x30)?;
                writer.write_u8(destination)?;
                writer.write_all(&hops)?;
            },
            Payload::RoutingSetRank { rank } => {
                writer.write_u8(0x31)?;
                writer.write_u8(rank)?;
            },
            Payload::RoutingAck =>
                writer.write_u8(0x32)?,
            Payload::RoutingRetrievePackets =>
                writer.write_u8(0x33)?,
            Payload::RoutingNoPackets =>
                writer.write_u8(0x34)?,

            Payload::MonitorRequest { channel, probe } => {
                writer.write_u8(0x40)?;
                writer.write_u16(channel)?;
                writer.write_u8(probe)?;
            },
            Payload::MonitorReply { value } => {
                writer.write_u8(0x41)?;
                writer.write_u64(value)?;
            },
            Payload::InjectionRequest { channel, overrd, value } => {
                writer.write_u8(0x50)?;
                writer.write_u16(channel)?;
                writer.write_u8(overrd)?;
                writer.write_u8(value)?;
            },
            Payload::InjectionStatusRequest { channel, overrd } => {
                writer.write_u8(0x51)?;
                writer.write_u16(channel)?;
                writer.write_u8(overrd)?;
            },
            Payload::InjectionStatusReply { value } => {
                writer.write_u8(0x52)?;
                writer.write_u8(value)?;
            },

            Payload::I2cStartRequest { busno } => {
                writer.write_u8(0x80)?;
                writer.write_u8(busno)?;
            },
            Payload::I2cRestartRequest { busno } => {
                writer.write_u8(0x81)?;
                writer.write_u8(busno)?;
            },
            Payload::I2cStopRequest { busno } => {
                writer.write_u8(0x82)?;
                writer.write_u8(busno)?;
            },
            Payload::I2cWriteRequest { busno, data } => {
                writer.write_u8(0x83)?;
                writer.write_u8(busno)?;
                writer.write_u8(data)?;
            },
            Payload::I2cWriteReply { succeeded, ack } => {
                writer.write_u8(0x84)?;
                writer.write_bool(succeeded)?;
                writer.write_bool(ack)?;
            },
            Payload::I2cReadRequest { busno, ack } => {
                writer.write_u8(0x85)?;
                writer.write_u8(busno)?;
                writer.write_bool(ack)?;
            },
            Payload::I2cReadReply { succeeded, data } => {
                writer.write_u8(0x86)?;
                writer.write_bool(succeeded)?;
                writer.write_u8(data)?;
            },
            Payload::I2cBasicReply { succeeded } => {
                writer.write_u8(0x87)?;
                writer.write_bool(succeeded)?;
            },
            Payload::I2cSwitchSelectRequest { busno, address, mask } => {
                writer.write_u8(0x88)?;
                writer.write_u8(busno)?;
                writer.write_u8(address)?;
                writer.write_u8(mask)?;
            },

            Payload::SpiSetConfigRequest { busno, flags, length, div, cs } => {
                writer.write_u8(0x90)?;
                writer.write_u8(busno)?;
                writer.write_u8(flags)?;
                writer.write_u8(length)?;
                writer.write_u8(div)?;
                writer.write_u8(cs)?;
            },
            Payload::SpiWriteRequest { busno, data } => {
                writer.write_u8(0x92)?;
                writer.write_u8(busno)?;
                writer.write_u32(data)?;
            },
            Payload::SpiReadRequest { busno } => {
                writer.write_u8(0x93)?;
                writer.write_u8(busno)?;
            },
            Payload::SpiReadReply { succeeded, data } => {
                writer.write_u8(0x94)?;
                writer.write_bool(succeeded)?;
                writer.write_u32(data)?;
            },
            Payload::SpiBasicReply { succeeded } => {
                writer.write_u8(0x95)?;
                writer.write_bool(succeeded)?;
            },

            Payload::AnalyzerHeaderRequest =>
                writer.write_u8(0xa0)?,
            Payload::AnalyzerHeader { sent_bytes, total_byte_count, overflow_occurred } => { 
                writer.write_u8(0xa1)?;
                writer.write_u32(sent_bytes)?;
                writer.write_u64(total_byte_count)?;
                writer.write_bool(overflow_occurred)?;
            },
            Payload::AnalyzerDataRequest => 
                writer.write_u8(0xa2)?,
            Payload::AnalyzerData { last, length, data } => {
                writer.write_u8(0xa3)?;
                writer.write_bool(last)?;
                writer.write_u16(length)?;
                writer.write_all(&data[0..length as usize])?;
            },

            Payload::DmaAddTraceRequest { id, status, trace, length } => {
                writer.write_u8(0xb0)?;
                writer.write_u32(id)?;
                writer.write_u8(status as u8)?;
                // trace may be broken down to fit within drtio aux memory limit
                // will be reconstructed by satellite
                writer.write_u16(length)?;
                writer.write_all(&trace[0..length as usize])?;
            },
            Payload::DmaAddTraceReply { id, succeeded } => {
                writer.write_u8(0xb1)?;
                writer.write_u32(id)?;
                writer.write_bool(succeeded)?;
            },
            Payload::DmaRemoveTraceRequest { id } => {
                writer.write_u8(0xb2)?;
                writer.write_u32(id)?;
            },
            Payload::DmaRemoveTraceReply { succeeded } => {
                writer.write_u8(0xb3)?;
                writer.write_bool(succeeded)?;
            },
            Payload::DmaPlaybackRequest { id, timestamp } => {
                writer.write_u8(0xb4)?;
                writer.write_u32(id)?;
                writer.write_u64(timestamp)?;
            },
            Payload::DmaPlaybackReply { succeeded } => {
                writer.write_u8(0xb5)?;
                writer.write_bool(succeeded)?;
            },
            Payload::DmaPlaybackStatus { id, error, channel, timestamp } => {
                writer.write_u8(0xb6)?;
                writer.write_u32(id)?;
                writer.write_u8(error)?;
                writer.write_u32(channel)?;
                writer.write_u64(timestamp)?;
            },

            Payload::SubkernelAddDataRequest { id, status, data, length } => {
                writer.write_u8(0xc0)?;
                writer.write_u32(id)?;
                writer.write_u8(status as u8)?;
                writer.write_u16(length)?;
                writer.write_all(&data[0..length as usize])?;
            },
            Payload::SubkernelAddDataReply { succeeded } => {
                writer.write_u8(0xc1)?;
                writer.write_bool(succeeded)?;
            },
            Payload::SubkernelLoadRunRequest { id, run } => {
                writer.write_u8(0xc4)?;
                writer.write_u32(id)?;
                writer.write_bool(run)?;
            },
            Payload::SubkernelLoadRunReply { succeeded } => {
                writer.write_u8(0xc5)?;
                writer.write_bool(succeeded)?;
            },
            Payload::SubkernelFinished { id, with_exception, exception_src } => {
                writer.write_u8(0xc8)?;
                writer.write_u32(id)?;
                writer.write_bool(with_exception)?;
                writer.write_u8(exception_src)?;
            },
            Payload::SubkernelExceptionRequest =>
                writer.write_u8(0xc9)?,
            Payload::SubkernelException { last, length, data } => {
                writer.write_u8(0xca)?;
                writer.write_bool(last)?;
                writer.write_u16(length)?;
                writer.write_all(&data[0..length as usize])?;
            },
            Payload::SubkernelMessage { id, status, data, length } => {
                writer.write_u8(0xcb)?;
                writer.write_u32(id)?;
                writer.write_u8(status as u8)?;
                writer.write_u16(length)?;
                writer.write_all(&data[0..length as usize])?;
            },
            Payload::SubkernelMessageAck =>
                writer.write_u8(0xcc)?,
        }
        Ok(())
    }

    pub fn expects_response(&self) -> bool {
        // returns true if the routable packet should elicit a response
        // e.g. reply, ACK packets end a conversation,
        // and firmware should not wait for response
        match self {
            Payload::DmaAddTraceReply { .. } | Payload::DmaRemoveTraceReply { .. } |
                Payload::DmaPlaybackReply { .. } | Payload::SubkernelLoadRunReply { .. } |
                Payload::SubkernelMessageAck { .. } | Payload::DmaPlaybackStatus { .. } |
                Payload::SubkernelFinished { .. } => false,
            _ => true
        }
    }
}
