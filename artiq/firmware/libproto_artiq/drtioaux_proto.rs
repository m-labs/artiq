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

#[derive(PartialEq, Debug)]
pub enum Packet {
    EchoRequest,
    EchoReply,
    ResetRequest,
    ResetAck,
    TSCAck,

    DestinationStatusRequest { destination: u8 },
    DestinationDownReply,
    DestinationOkReply,
    DestinationSequenceErrorReply { channel: u16 },
    DestinationCollisionReply { channel: u16 },
    DestinationBusyReply { channel: u16 },

    RoutingSetPath { destination: u8, hops: [u8; 32] },
    RoutingSetRank { rank: u8 },
    RoutingAck,

    MonitorRequest { destination: u8, channel: u16, probe: u8 },
    MonitorReply { value: u32 },
    InjectionRequest { destination: u8, channel: u16, overrd: u8, value: u8 },
    InjectionStatusRequest { destination: u8, channel: u16, overrd: u8 },
    InjectionStatusReply { value: u8 },

    I2cStartRequest { destination: u8, busno: u8 },
    I2cRestartRequest { destination: u8, busno: u8 },
    I2cStopRequest { destination: u8, busno: u8 },
    I2cWriteRequest { destination: u8, busno: u8, data: u8 },
    I2cWriteReply { succeeded: bool, ack: bool },
    I2cReadRequest { destination: u8, busno: u8, ack: bool },
    I2cReadReply { succeeded: bool, data: u8 },
    I2cBasicReply { succeeded: bool },

    SpiSetConfigRequest { destination: u8, busno: u8, flags: u8, length: u8, div: u8, cs: u8 },
    SpiWriteRequest { destination: u8, busno: u8, data: u32 },
    SpiReadRequest { destination: u8, busno: u8 },
    SpiReadReply { succeeded: bool, data: u32 },
    SpiBasicReply { succeeded: bool },

    JdacBasicRequest { destination: u8, dacno: u8, reqno: u8, param: u8 },
    JdacBasicReply { succeeded: bool, retval: u8 },
}

impl Packet {
    pub fn read_from<R>(reader: &mut R) -> Result<Self, Error<R::ReadError>>
        where R: Read + ?Sized
    {
        Ok(match reader.read_u8()? {
            0x00 => Packet::EchoRequest,
            0x01 => Packet::EchoReply,
            0x02 => Packet::ResetRequest,
            0x03 => Packet::ResetAck,
            0x04 => Packet::TSCAck,

            0x20 => Packet::DestinationStatusRequest {
                destination: reader.read_u8()?
            },
            0x21 => Packet::DestinationDownReply,
            0x22 => Packet::DestinationOkReply,
            0x23 => Packet::DestinationSequenceErrorReply {
                channel: reader.read_u16()?
            },
            0x24 => Packet::DestinationCollisionReply {
                channel: reader.read_u16()?
            },
            0x25 => Packet::DestinationBusyReply {
                channel: reader.read_u16()?
            },

            0x30 => {
                let destination = reader.read_u8()?;
                let mut hops = [0; 32];
                reader.read_exact(&mut hops)?;
                Packet::RoutingSetPath {
                    destination: destination,
                    hops: hops
                }
            },
            0x31 => Packet::RoutingSetRank {
                rank: reader.read_u8()?
            },
            0x32 => Packet::RoutingAck,

            0x40 => Packet::MonitorRequest {
                destination: reader.read_u8()?,
                channel: reader.read_u16()?,
                probe: reader.read_u8()?
            },
            0x41 => Packet::MonitorReply {
                value: reader.read_u32()?
            },
            0x50 => Packet::InjectionRequest {
                destination: reader.read_u8()?,
                channel: reader.read_u16()?,
                overrd: reader.read_u8()?,
                value: reader.read_u8()?
            },
            0x51 => Packet::InjectionStatusRequest {
                destination: reader.read_u8()?,
                channel: reader.read_u16()?,
                overrd: reader.read_u8()?
            },
            0x52 => Packet::InjectionStatusReply {
                value: reader.read_u8()?
            },

            0x80 => Packet::I2cStartRequest {
                destination: reader.read_u8()?,
                busno: reader.read_u8()?
            },
            0x81 => Packet::I2cRestartRequest {
                destination: reader.read_u8()?,
                busno: reader.read_u8()?
            },
            0x82 => Packet::I2cStopRequest {
                destination: reader.read_u8()?,
                busno: reader.read_u8()?
            },
            0x83 => Packet::I2cWriteRequest {
                destination: reader.read_u8()?,
                busno: reader.read_u8()?,
                data: reader.read_u8()?
            },
            0x84 => Packet::I2cWriteReply {
                succeeded: reader.read_bool()?,
                ack: reader.read_bool()?
            },
            0x85 => Packet::I2cReadRequest {
                destination: reader.read_u8()?,
                busno: reader.read_u8()?,
                ack: reader.read_bool()?
            },
            0x86 => Packet::I2cReadReply {
                succeeded: reader.read_bool()?,
                data: reader.read_u8()?
            },
            0x87 => Packet::I2cBasicReply {
                succeeded: reader.read_bool()?
            },

            0x90 => Packet::SpiSetConfigRequest {
                destination: reader.read_u8()?,
                busno: reader.read_u8()?,
                flags: reader.read_u8()?,
                length: reader.read_u8()?,
                div: reader.read_u8()?,
                cs: reader.read_u8()?
            },
            /* 0x91: was Packet::SpiSetXferRequest */
            0x92 => Packet::SpiWriteRequest {
                destination: reader.read_u8()?,
                busno: reader.read_u8()?,
                data: reader.read_u32()?
            },
            0x93 => Packet::SpiReadRequest {
                destination: reader.read_u8()?,
                busno: reader.read_u8()?
            },
            0x94 => Packet::SpiReadReply {
                succeeded: reader.read_bool()?,
                data: reader.read_u32()?
            },
            0x95 => Packet::SpiBasicReply {
                succeeded: reader.read_bool()?
            },

            0xa0 => Packet::JdacBasicRequest {
                destination: reader.read_u8()?,
                dacno: reader.read_u8()?,
                reqno: reader.read_u8()?,
                param: reader.read_u8()?,
            },
            0xa1 => Packet::JdacBasicReply {
                succeeded: reader.read_bool()?,
                retval: reader.read_u8()?
            },

            ty => return Err(Error::UnknownPacket(ty))
        })
    }

    pub fn write_to<W>(&self, writer: &mut W) -> Result<(), IoError<W::WriteError>>
        where W: Write + ?Sized
    {
        match *self {
            Packet::EchoRequest =>
                writer.write_u8(0x00)?,
            Packet::EchoReply =>
                writer.write_u8(0x01)?,
            Packet::ResetRequest =>
                writer.write_u8(0x02)?,
            Packet::ResetAck =>
                writer.write_u8(0x03)?,
            Packet::TSCAck =>
                writer.write_u8(0x04)?,

            Packet::DestinationStatusRequest { destination } => {
                writer.write_u8(0x20)?;
                writer.write_u8(destination)?;
            },
            Packet::DestinationDownReply =>
                writer.write_u8(0x21)?,
            Packet::DestinationOkReply =>
                writer.write_u8(0x22)?,
            Packet::DestinationSequenceErrorReply { channel } => {
                writer.write_u8(0x23)?;
                writer.write_u16(channel)?;
            },
            Packet::DestinationCollisionReply { channel } => {
                writer.write_u8(0x24)?;
                writer.write_u16(channel)?;
            },
            Packet::DestinationBusyReply { channel } => {
                writer.write_u8(0x25)?;
                writer.write_u16(channel)?;
            },

            Packet::RoutingSetPath { destination, hops } => {
                writer.write_u8(0x30)?;
                writer.write_u8(destination)?;
                writer.write_all(&hops)?;
            },
            Packet::RoutingSetRank { rank } => {
                writer.write_u8(0x31)?;
                writer.write_u8(rank)?;
            },
            Packet::RoutingAck =>
                writer.write_u8(0x32)?,

            Packet::MonitorRequest { destination, channel, probe } => {
                writer.write_u8(0x40)?;
                writer.write_u8(destination)?;
                writer.write_u16(channel)?;
                writer.write_u8(probe)?;
            },
            Packet::MonitorReply { value } => {
                writer.write_u8(0x41)?;
                writer.write_u32(value)?;
            },
            Packet::InjectionRequest { destination, channel, overrd, value } => {
                writer.write_u8(0x50)?;
                writer.write_u8(destination)?;
                writer.write_u16(channel)?;
                writer.write_u8(overrd)?;
                writer.write_u8(value)?;
            },
            Packet::InjectionStatusRequest { destination, channel, overrd } => {
                writer.write_u8(0x51)?;
                writer.write_u8(destination)?;
                writer.write_u16(channel)?;
                writer.write_u8(overrd)?;
            },
            Packet::InjectionStatusReply { value } => {
                writer.write_u8(0x52)?;
                writer.write_u8(value)?;
            },

            Packet::I2cStartRequest { destination, busno } => {
                writer.write_u8(0x80)?;
                writer.write_u8(destination)?;
                writer.write_u8(busno)?;
            },
            Packet::I2cRestartRequest { destination, busno } => {
                writer.write_u8(0x81)?;
                writer.write_u8(destination)?;
                writer.write_u8(busno)?;
            },
            Packet::I2cStopRequest { destination, busno } => {
                writer.write_u8(0x82)?;
                writer.write_u8(destination)?;
                writer.write_u8(busno)?;
            },
            Packet::I2cWriteRequest { destination, busno, data } => {
                writer.write_u8(0x83)?;
                writer.write_u8(destination)?;
                writer.write_u8(busno)?;
                writer.write_u8(data)?;
            },
            Packet::I2cWriteReply { succeeded, ack } => {
                writer.write_u8(0x84)?;
                writer.write_bool(succeeded)?;
                writer.write_bool(ack)?;
            },
            Packet::I2cReadRequest { destination, busno, ack } => {
                writer.write_u8(0x85)?;
                writer.write_u8(destination)?;
                writer.write_u8(busno)?;
                writer.write_bool(ack)?;
            },
            Packet::I2cReadReply { succeeded, data } => {
                writer.write_u8(0x86)?;
                writer.write_bool(succeeded)?;
                writer.write_u8(data)?;
            },
            Packet::I2cBasicReply { succeeded } => {
                writer.write_u8(0x87)?;
                writer.write_bool(succeeded)?;
            },

            Packet::SpiSetConfigRequest { destination, busno, flags, length, div, cs } => {
                writer.write_u8(0x90)?;
                writer.write_u8(destination)?;
                writer.write_u8(busno)?;
                writer.write_u8(flags)?;
                writer.write_u8(length)?;
                writer.write_u8(div)?;
                writer.write_u8(cs)?;
            },
            Packet::SpiWriteRequest { destination, busno, data } => {
                writer.write_u8(0x92)?;
                writer.write_u8(destination)?;
                writer.write_u8(busno)?;
                writer.write_u32(data)?;
            },
            Packet::SpiReadRequest { destination, busno } => {
                writer.write_u8(0x93)?;
                writer.write_u8(destination)?;
                writer.write_u8(busno)?;
            },
            Packet::SpiReadReply { succeeded, data } => {
                writer.write_u8(0x94)?;
                writer.write_bool(succeeded)?;
                writer.write_u32(data)?;
            },
            Packet::SpiBasicReply { succeeded } => {
                writer.write_u8(0x95)?;
                writer.write_bool(succeeded)?;
            },

            Packet::JdacBasicRequest { destination, dacno, reqno, param } => {
                writer.write_u8(0xa0)?;
                writer.write_u8(destination)?;
                writer.write_u8(dacno)?;
                writer.write_u8(reqno)?;
                writer.write_u8(param)?;
            }
            Packet::JdacBasicReply { succeeded, retval } => {
                writer.write_u8(0xa1)?;
                writer.write_bool(succeeded)?;
                writer.write_u8(retval)?;
            },
        }
        Ok(())
    }
}
