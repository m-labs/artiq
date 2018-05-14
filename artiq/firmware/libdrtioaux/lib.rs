#![no_std]
#![feature(never_type)]

extern crate crc;

extern crate io;
extern crate board;

use core::slice;
use core::result;
use core::fmt;

use io::{Read, Write, Error as IoError};
use io::proto::{ProtoRead, ProtoWrite};

pub type Result<T, E> = result::Result<T, Error<E>>;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error<T> {
    UnknownPacket(u8),
    CorruptedPacket,
    TimedOut,
    NoRoute,
    GatewareError,
    Io(IoError<T>),
    Other(T)
}

impl<T: fmt::Display> fmt::Display for Error<T> {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            &Error::UnknownPacket(ty) =>
                write!(f, "unknown packet type {:#02x}", ty),
            &Error::CorruptedPacket =>
                write!(f, "packet CRC failed"),
            &Error::TimedOut =>
                write!(f, "timed out waiting for data"),
            &Error::NoRoute =>
                write!(f, "invalid node number"),
            &Error::GatewareError =>
                write!(f, "gateware reported error"),
            &Error::Io(ref io) =>
                write!(f, "I/O error ({})", io),
            &Error::Other(ref err) =>
                write!(f, "{}", err)
        }
    }
}

impl<T> From<T> for Error<T> {
    fn from(value: T) -> Error<T> {
        Error::Other(value)
    }
}

impl<T> From<IoError<T>> for Error<T> {
    fn from(value: IoError<T>) -> Error<T> {
        Error::Io(value)
    }
}

#[derive(Debug)]
pub enum Packet {
    EchoRequest,
    EchoReply,
    ResetRequest { phy: bool },
    ResetAck,

    RtioErrorRequest,
    RtioNoErrorReply,
    RtioErrorSequenceErrorReply { channel: u16 },
    RtioErrorCollisionReply { channel: u16 },
    RtioErrorBusyReply { channel: u16 },

    MonitorRequest { channel: u16, probe: u8 },
    MonitorReply { value: u32 },
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

    SpiSetConfigRequest { busno: u8, flags: u8, length: u8, div: u8, cs: u8 },
    SpiWriteRequest { busno: u8, data: u32 },
    SpiReadRequest { busno: u8 },
    SpiReadReply { succeeded: bool, data: u32 },
    SpiBasicReply { succeeded: bool },
}

impl Packet {
    pub fn read_from<T: Read>(reader: &mut T) -> Result<Packet, T::ReadError> {
        Ok(match reader.read_u8()? {
            0x00 => Packet::EchoRequest,
            0x01 => Packet::EchoReply,
            0x02 => Packet::ResetRequest {
                phy: reader.read_bool()?
            },
            0x03 => Packet::ResetAck,

            0x20 => Packet::RtioErrorRequest,
            0x21 => Packet::RtioNoErrorReply,
            0x22 => Packet::RtioErrorSequenceErrorReply {
                channel: reader.read_u16()?
            },
            0x23 => Packet::RtioErrorCollisionReply {
                channel: reader.read_u16()?
            },
            0x24 => Packet::RtioErrorBusyReply {
                channel: reader.read_u16()?
            },

            0x40 => Packet::MonitorRequest {
                channel: reader.read_u16()?,
                probe: reader.read_u8()?
            },
            0x41 => Packet::MonitorReply {
                value: reader.read_u32()?
            },
            0x50 => Packet::InjectionRequest {
                channel: reader.read_u16()?,
                overrd: reader.read_u8()?,
                value: reader.read_u8()?
            },
            0x51 => Packet::InjectionStatusRequest {
                channel: reader.read_u16()?,
                overrd: reader.read_u8()?
            },
            0x52 => Packet::InjectionStatusReply {
                value: reader.read_u8()?
            },

            0x80 => Packet::I2cStartRequest {
                busno: reader.read_u8()?
            },
            0x81 => Packet::I2cRestartRequest {
                busno: reader.read_u8()?
            },
            0x82 => Packet::I2cStopRequest {
                busno: reader.read_u8()?
            },
            0x83 => Packet::I2cWriteRequest {
                busno: reader.read_u8()?,
                data: reader.read_u8()?
            },
            0x84 => Packet::I2cWriteReply {
                succeeded: reader.read_bool()?,
                ack: reader.read_bool()?
            },
            0x85 => Packet::I2cReadRequest {
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
                busno: reader.read_u8()?,
                flags: reader.read_u8()?,
                length: reader.read_u8()?,
                div: reader.read_u8()?,
                cs: reader.read_u8()?
            },
            /* 0x91: was Packet::SpiSetXferRequest */
            0x92 => Packet::SpiWriteRequest {
                busno: reader.read_u8()?,
                data: reader.read_u32()?
            },
            0x93 => Packet::SpiReadRequest {
                busno: reader.read_u8()?
            },
            0x94 => Packet::SpiReadReply {
                succeeded: reader.read_bool()?,
                data: reader.read_u32()?
            },
            0x95 => Packet::SpiBasicReply {
                succeeded: reader.read_bool()?
            },

            ty => return Err(Error::UnknownPacket(ty))
        })
    }

    pub fn write_to<T: Write>(&self, writer: &mut T) -> Result<(), T::WriteError> {
        match *self {
            Packet::EchoRequest =>
                writer.write_u8(0x00)?,
            Packet::EchoReply =>
                writer.write_u8(0x01)?,
            Packet::ResetRequest { phy } => {
                writer.write_u8(0x02)?;
                writer.write_bool(phy)?;
            },
            Packet::ResetAck =>
                writer.write_u8(0x03)?,

            Packet::RtioErrorRequest =>
                writer.write_u8(0x20)?,
            Packet::RtioNoErrorReply =>
                writer.write_u8(0x21)?,
            Packet::RtioErrorSequenceErrorReply { channel } => {
                writer.write_u8(0x22)?;
                writer.write_u16(channel)?;
            },
            Packet::RtioErrorCollisionReply { channel } => {
                writer.write_u8(0x23)?;
                writer.write_u16(channel)?;
            },
            Packet::RtioErrorBusyReply { channel } => {
                writer.write_u8(0x24)?;
                writer.write_u16(channel)?;
            },

            Packet::MonitorRequest { channel, probe } => {
                writer.write_u8(0x40)?;
                writer.write_u16(channel)?;
                writer.write_u8(probe)?;
            },
            Packet::MonitorReply { value } => {
                writer.write_u8(0x41)?;
                writer.write_u32(value)?;
            },
            Packet::InjectionRequest { channel, overrd, value } => {
                writer.write_u8(0x50)?;
                writer.write_u16(channel)?;
                writer.write_u8(overrd)?;
                writer.write_u8(value)?;
            },
            Packet::InjectionStatusRequest { channel, overrd } => {
                writer.write_u8(0x51)?;
                writer.write_u16(channel)?;
                writer.write_u8(overrd)?;
            },
            Packet::InjectionStatusReply { value } => {
                writer.write_u8(0x52)?;
                writer.write_u8(value)?;
            },

            Packet::I2cStartRequest { busno } => {
                writer.write_u8(0x80)?;
                writer.write_u8(busno)?;
            },
            Packet::I2cRestartRequest { busno } => {
                writer.write_u8(0x81)?;
                writer.write_u8(busno)?;
            },
            Packet::I2cStopRequest { busno } => {
                writer.write_u8(0x82)?;
                writer.write_u8(busno)?;
            },
            Packet::I2cWriteRequest { busno, data } => {
                writer.write_u8(0x83)?;
                writer.write_u8(busno)?;
                writer.write_u8(data)?;
            },
            Packet::I2cWriteReply { succeeded, ack } => {
                writer.write_u8(0x84)?;
                writer.write_bool(succeeded)?;
                writer.write_bool(ack)?;
            },
            Packet::I2cReadRequest { busno, ack } => {
                writer.write_u8(0x85)?;
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

            Packet::SpiSetConfigRequest { busno, flags, length, div, cs } => {
                writer.write_u8(0x90)?;
                writer.write_u8(busno)?;
                writer.write_u8(flags)?;
                writer.write_u8(length)?;
                writer.write_u8(div)?;
                writer.write_u8(cs)?;
            },
            Packet::SpiWriteRequest { busno, data } => {
                writer.write_u8(0x92)?;
                writer.write_u8(busno)?;
                writer.write_u32(data)?;
            },
            Packet::SpiReadRequest { busno } => {
                writer.write_u8(0x93)?;
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
        }
        Ok(())
    }
}

#[cfg(has_drtio)]
pub mod hw;
