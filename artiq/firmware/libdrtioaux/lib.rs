#![no_std]

#[macro_use]
extern crate std_artiq as std;
extern crate board;
extern crate byteorder;

mod proto;
#[cfg(has_drtio)]
mod crc32;

use std::io::{self, Read, Write};
#[cfg(has_drtio)]
use core::slice;
use proto::*;

#[derive(Debug)]
pub enum Packet {
    EchoRequest,
    EchoReply,

    RtioErrorRequest,
    RtioNoErrorReply,
    RtioErrorCollisionReply,
    RtioErrorBusyReply,

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

    SpiSetConfigRequest { busno: u8, flags: u8, write_div: u8, read_div: u8 },
    SpiSetXferRequest { busno: u8, chip_select: u16, write_length: u8, read_length: u8 },
    SpiWriteRequest { busno: u8, data: u32 },
    SpiReadRequest { busno: u8 },
    SpiReadReply { succeeded: bool, data: u32 },
    SpiBasicReply { succeeded: bool },
}

impl Packet {
    pub fn read_from(reader: &mut Read) -> io::Result<Packet> {
        Ok(match read_u8(reader)? {
            0x00 => Packet::EchoRequest,
            0x01 => Packet::EchoReply,

            0x20 => Packet::RtioErrorRequest,
            0x21 => Packet::RtioNoErrorReply,
            0x22 => Packet::RtioErrorCollisionReply,
            0x23 => Packet::RtioErrorBusyReply,

            0x40 => Packet::MonitorRequest {
                channel: read_u16(reader)?,
                probe: read_u8(reader)?
            },
            0x41 => Packet::MonitorReply {
                value: read_u32(reader)?
            },
            0x50 => Packet::InjectionRequest {
                channel: read_u16(reader)?,
                overrd: read_u8(reader)?,
                value: read_u8(reader)?
            },
            0x51 => Packet::InjectionStatusRequest {
                channel: read_u16(reader)?,
                overrd: read_u8(reader)?
            },
            0x52 => Packet::InjectionStatusReply {
                value: read_u8(reader)?
            },

            0x80 => Packet::I2cStartRequest {
                busno: read_u8(reader)?
            },
            0x81 => Packet::I2cRestartRequest {
                busno: read_u8(reader)?
            },
            0x82 => Packet::I2cStopRequest {
                busno: read_u8(reader)?
            },
            0x83 => Packet::I2cWriteRequest {
                busno: read_u8(reader)?,
                data: read_u8(reader)?
            },
            0x84 => Packet::I2cWriteReply {
                succeeded: read_bool(reader)?,
                ack: read_bool(reader)?
            },
            0x85 => Packet::I2cReadRequest {
                busno: read_u8(reader)?,
                ack: read_bool(reader)?
            },
            0x86 => Packet::I2cReadReply {
                succeeded: read_bool(reader)?,
                data: read_u8(reader)?
            },
            0x87 => Packet::I2cBasicReply {
                succeeded: read_bool(reader)?
            },

            0x90 => Packet::SpiSetConfigRequest {
                busno: read_u8(reader)?,
                flags: read_u8(reader)?,
                write_div: read_u8(reader)?,
                read_div: read_u8(reader)?
            },
            0x91 => Packet::SpiSetXferRequest {
                busno: read_u8(reader)?,
                chip_select: read_u16(reader)?,
                write_length: read_u8(reader)?,
                read_length: read_u8(reader)?
            },
            0x92 => Packet::SpiWriteRequest {
                busno: read_u8(reader)?,
                data: read_u32(reader)?
            },
            0x93 => Packet::SpiReadRequest {
                busno: read_u8(reader)?
            },
            0x94 => Packet::SpiReadReply {
                succeeded: read_bool(reader)?,
                data: read_u32(reader)?
            },
            0x95 => Packet::SpiBasicReply {
                succeeded: read_bool(reader)?
            },

            _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown packet type"))
        })
    }

    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        match *self {
            Packet::EchoRequest => write_u8(writer, 0x00)?,
            Packet::EchoReply => write_u8(writer, 0x01)?,

            Packet::RtioErrorRequest => write_u8(writer, 0x20)?,
            Packet::RtioNoErrorReply => write_u8(writer, 0x21)?,
            Packet::RtioErrorCollisionReply => write_u8(writer, 0x22)?,
            Packet::RtioErrorBusyReply => write_u8(writer, 0x23)?,

            Packet::MonitorRequest { channel, probe } => {
                write_u8(writer, 0x40)?;
                write_u16(writer, channel)?;
                write_u8(writer, probe)?;
            },
            Packet::MonitorReply { value } => {
                write_u8(writer, 0x41)?;
                write_u32(writer, value)?;
            },
            Packet::InjectionRequest { channel, overrd, value } => {
                write_u8(writer, 0x50)?;
                write_u16(writer, channel)?;
                write_u8(writer, overrd)?;
                write_u8(writer, value)?;
            },
            Packet::InjectionStatusRequest { channel, overrd } => {
                write_u8(writer, 0x51)?;
                write_u16(writer, channel)?;
                write_u8(writer, overrd)?;
            },
            Packet::InjectionStatusReply { value } => {
                write_u8(writer, 0x52)?;
                write_u8(writer, value)?;
            },

            Packet::I2cStartRequest { busno } => {
                write_u8(writer, 0x80)?;
                write_u8(writer, busno)?;
            },
            Packet::I2cRestartRequest { busno } => {
                write_u8(writer, 0x81)?;
                write_u8(writer, busno)?;
            },
            Packet::I2cStopRequest { busno } => {
                write_u8(writer, 0x82)?;
                write_u8(writer, busno)?;
            },
            Packet::I2cWriteRequest { busno, data } => {
                write_u8(writer, 0x83)?;
                write_u8(writer, busno)?;
                write_u8(writer, data)?;
            },
            Packet::I2cWriteReply { succeeded, ack } => {
                write_u8(writer, 0x84)?;
                write_bool(writer, succeeded)?;
                write_bool(writer, ack)?;
            },
            Packet::I2cReadRequest { busno, ack } => {
                write_u8(writer, 0x85)?;
                write_u8(writer, busno)?;
                write_bool(writer, ack)?;
            },
            Packet::I2cReadReply { succeeded, data } => {
                write_u8(writer, 0x86)?;
                write_bool(writer, succeeded)?;
                write_u8(writer, data)?;
            },
            Packet::I2cBasicReply { succeeded } => {
                write_u8(writer, 0x87)?;
                write_bool(writer, succeeded)?;
            },

            Packet::SpiSetConfigRequest { busno, flags, write_div, read_div } => {
                write_u8(writer, 0x90)?;
                write_u8(writer, busno)?;
                write_u8(writer, flags)?;
                write_u8(writer, write_div)?;
                write_u8(writer, read_div)?;
            },
            Packet::SpiSetXferRequest { busno, chip_select, write_length, read_length } => {
                write_u8(writer, 0x91)?;
                write_u8(writer, busno)?;
                write_u16(writer, chip_select)?;
                write_u8(writer, write_length)?;
                write_u8(writer, read_length)?;
            },
            Packet::SpiWriteRequest { busno, data } => {
                write_u8(writer, 0x92)?;
                write_u8(writer, busno)?;
                write_u32(writer, data)?;
            },
            Packet::SpiReadRequest { busno } => {
                write_u8(writer, 0x93)?;
                write_u8(writer, busno)?;
            },
            Packet::SpiReadReply { succeeded, data } => {
                write_u8(writer, 0x94)?;
                write_bool(writer, succeeded)?;
                write_u32(writer, data)?;
            },
            Packet::SpiBasicReply { succeeded } => {
                write_u8(writer, 0x95)?;
                write_bool(writer, succeeded)?;
            },
        }
        Ok(())
    }
}

#[cfg(has_drtio)]
pub mod hw {
    use super::*;
    use std::io::Cursor;

    fn rx_has_error(linkno: u8) -> bool {
        let linkno = linkno as usize;
        unsafe {
            let error = (board::csr::DRTIO[linkno].aux_rx_error_read)() != 0;
            if error {
                (board::csr::DRTIO[linkno].aux_rx_error_write)(1)
            }
            error
        }
    }

    struct RxBuffer(u8, &'static [u8]);

    impl Drop for RxBuffer {
        fn drop(&mut self) {
            unsafe {
                (board::csr::DRTIO[self.0 as usize].aux_rx_present_write)(1);
            }
        }
    }

    fn rx_get_buffer(linkno: u8) -> Option<RxBuffer> {
        let linkidx = linkno as usize;
        unsafe {
            if (board::csr::DRTIO[linkidx].aux_rx_present_read)() == 1 {
                let length = (board::csr::DRTIO[linkidx].aux_rx_length_read)();
                let base = board::mem::DRTIO_AUX[linkidx].base + board::mem::DRTIO_AUX[linkidx].size/2; 
                let sl = slice::from_raw_parts(base as *mut u8, length as usize);
                Some(RxBuffer(linkno, sl))
            } else {
                None
            }
        }
    }

    pub fn recv_link(linkno: u8) -> io::Result<Option<Packet>> {
        if rx_has_error(linkno) {
            return Err(io::Error::new(io::ErrorKind::Other, "gateware reported error"))
        }
        let buffer = rx_get_buffer(linkno);
        match buffer {
            Some(rxb) => {
                let slice = rxb.1;
                let mut reader = Cursor::new(slice);

                let len = slice.len();
                if len < 8 {
                    return Err(io::Error::new(io::ErrorKind::InvalidData, "packet too short"))
                }
                let computed_crc = crc32::checksum_ieee(&reader.get_ref()[0..len-4]);
                reader.set_position((len-4) as u64);
                let crc = read_u32(&mut reader)?;
                if crc != computed_crc {
                    return Err(io::Error::new(io::ErrorKind::InvalidData, "packet CRC failed"))
                }
                reader.set_position(0);

                let packet_r = Packet::read_from(&mut reader);
                match packet_r {
                    Ok(packet) => Ok(Some(packet)),
                    Err(e) => Err(e)
                }
            }
            None => Ok(None)
        }
    }

    pub fn recv_timeout_link(linkno: u8, timeout_ms: Option<u64>) -> io::Result<Packet> {
        let timeout_ms = timeout_ms.unwrap_or(10);
        let limit = board::clock::get_ms() + timeout_ms;
        while board::clock::get_ms() < limit {
            match recv_link(linkno) {
                Ok(None) => (),
                Ok(Some(packet)) => return Ok(packet),
                Err(e) => return Err(e)
            }
        }
        return Err(io::Error::new(io::ErrorKind::TimedOut, "timed out waiting for data"))
    }

    fn tx_get_buffer(linkno: u8) -> &'static mut [u8] {
        let linkno = linkno as usize;
        unsafe {
            while (board::csr::DRTIO[linkno].aux_tx_read)() != 0 {}
            let base = board::mem::DRTIO_AUX[linkno].base;
            let size = board::mem::DRTIO_AUX[linkno].size/2;
            slice::from_raw_parts_mut(base as *mut u8, size)
        }
    }

    fn tx_ack_buffer(linkno: u8, length: u16) {
        let linkno = linkno as usize;
        unsafe {
            (board::csr::DRTIO[linkno].aux_tx_length_write)(length);
            (board::csr::DRTIO[linkno].aux_tx_write)(1)
        }
    }

    pub fn send_link(linkno: u8, packet: &Packet) -> io::Result<()> {
        let sl = tx_get_buffer(linkno);

        let mut writer = Cursor::new(sl);
        packet.write_to(&mut writer)?;
        let mut len = writer.position();

        let padding = 4 - (len % 4);
        if padding != 4 {
            for _ in 0..padding {
                write_u8(&mut writer, 0)?;
            }
            len += padding;
        }

        let crc = crc32::checksum_ieee(&writer.get_ref()[0..len as usize]);
        write_u32(&mut writer, crc)?;
        len += 4;

        tx_ack_buffer(linkno, len as u16);

        Ok(())
    }

    // TODO: routing
    fn get_linkno(nodeno: u8) -> io::Result<u8> {
        if nodeno == 0 || nodeno as usize > board::csr::DRTIO.len() {
            return Err(io::Error::new(io::ErrorKind::NotFound, "invalid node number"))
        }
        Ok(nodeno - 1)
    }

    pub fn recv(nodeno: u8) -> io::Result<Option<Packet>> {
        let linkno = get_linkno(nodeno)?;
        recv_link(linkno)
    }

    pub fn recv_timeout(nodeno: u8, timeout_ms: Option<u64>) -> io::Result<Packet> {
        let linkno = get_linkno(nodeno)?;
        recv_timeout_link(linkno, timeout_ms)
    }

    pub fn send(nodeno: u8, packet: &Packet) -> io::Result<()> {
        let linkno = get_linkno(nodeno)?;
        send_link(linkno, packet)
    }
}
