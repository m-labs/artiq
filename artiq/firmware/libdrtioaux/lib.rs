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
    InjectionStatusReply { value: u8 }
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
            }
        }
        Ok(())
    }
}

#[cfg(has_drtio)]
pub mod hw {
    use super::*;
    use std::io::Cursor;

    const AUX_TX_BASE: usize = board::mem::DRTIO_AUX_BASE;
    const AUX_TX_SIZE: usize = board::mem::DRTIO_AUX_SIZE/2;
    const AUX_RX_BASE: usize = AUX_TX_BASE + AUX_TX_SIZE;

    fn rx_has_error() -> bool {
        unsafe {
            let error = board::csr::drtio::aux_rx_error_read() != 0;
            if error {
                board::csr::drtio::aux_rx_error_write(1)
            }
            error
        }
    }

    struct RxBuffer(&'static [u8]);

    impl Drop for RxBuffer {
        fn drop(&mut self) {
            unsafe {
                board::csr::drtio::aux_rx_present_write(1);
            }
        }
    }

    fn rx_get_buffer() -> Option<RxBuffer> {
        unsafe {
            if board::csr::drtio::aux_rx_present_read() == 1 {
                let length = board::csr::drtio::aux_rx_length_read();
                let sl = slice::from_raw_parts(AUX_RX_BASE as *mut u8, length as usize);
                Some(RxBuffer(sl))
            } else {
                None
            }
        }
    }

    pub fn recv() -> io::Result<Option<Packet>> {
        if rx_has_error() {
            return Err(io::Error::new(io::ErrorKind::Other, "gateware reported error"))
        }
        let buffer = rx_get_buffer();
        match buffer {
            Some(rxb) => {
                let slice = rxb.0;
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

    pub fn recv_timeout(timeout_ms: u64) -> io::Result<Packet> {
        let limit = board::clock::get_ms() + timeout_ms;
        while board::clock::get_ms() < limit {
            match recv() {
                Ok(None) => (),
                Ok(Some(packet)) => return Ok(packet),
                Err(e) => return Err(e)
            }
        }
        return Err(io::Error::new(io::ErrorKind::TimedOut, "timed out waiting for data"))
    }

    fn tx_get_buffer() -> &'static mut [u8] {
        unsafe {
            while board::csr::drtio::aux_tx_read() != 0 {}
            slice::from_raw_parts_mut(AUX_TX_BASE as *mut u8, AUX_TX_SIZE)
        }
    }

    fn tx_ack_buffer(length: u16) {
        unsafe {
            board::csr::drtio::aux_tx_length_write(length);
            board::csr::drtio::aux_tx_write(1)
        }
    }

    pub fn send(packet: &Packet) -> io::Result<()> {
        let sl = tx_get_buffer();

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

        tx_ack_buffer(len as u16);

        Ok(())
    }
}
