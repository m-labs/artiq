#![no_std]

#[macro_use]
extern crate std_artiq as std;
#[macro_use]
extern crate log;
extern crate board;
extern crate byteorder;

mod proto;
mod crc32;

use std::io::{self, Read, Write};
use core::slice;
use proto::*;

#[derive(Debug)]
pub enum Packet {
    EchoRequest,
    EchoReply,
    //MonitorRequest,
    //MonitorReply
}

impl Packet {
    pub fn read_from(reader: &mut Read) -> io::Result<Packet> {
        Ok(match read_u8(reader)? {
            0 => Packet::EchoRequest,
            1 => Packet::EchoReply,
            _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown packet type"))
        })
    }

    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        match *self {
            Packet::EchoRequest => write_u8(writer, 0)?,
            Packet::EchoReply => write_u8(writer, 1)?
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
