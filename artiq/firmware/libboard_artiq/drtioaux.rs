use core::{slice, fmt, result};
use crc;

use io::{Cursor, Error as IoError};
use io::proto::{ProtoRead, ProtoWrite};
use board;

pub use proto::drtioaux_proto::Packet;

pub type Result<T> = result::Result<T, Error>;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    CorruptedPacket,
    TimedOut,
    NoRoute,
    GatewareError,
    Io(IoError<!>)
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            &Error::CorruptedPacket =>
                write!(f, "packet CRC failed"),
            &Error::TimedOut =>
                write!(f, "timed out waiting for data"),
            &Error::NoRoute =>
                write!(f, "invalid node number"),
            &Error::GatewareError =>
                write!(f, "gateware reported error"),
            &Error::Io(ref io) =>
                write!(f, "I/O error ({})", io)
        }
    }
}

impl From<IoError<!>> for Error {
    fn from(value: IoError<!>) -> Error {
        Error::Io(value)
    }
}

pub fn reset(linkno: u8) {
    let linkno = linkno as usize;
    unsafe {
        // clear buffer first to limit race window with buffer overflow
        // error. We assume the CPU is fast enough so that no two packets
        // will be received between the buffer and the error flag are cleared.
        (board::csr::DRTIO[linkno].aux_rx_present_write)(1);
        (board::csr::DRTIO[linkno].aux_rx_error_write)(1);
    }
}

fn has_rx_error(linkno: u8) -> bool {
    let linkno = linkno as usize;
    unsafe {
        let error = (board::csr::DRTIO[linkno].aux_rx_error_read)() != 0;
        if error {
            (board::csr::DRTIO[linkno].aux_rx_error_write)(1)
        }
        error
    }
}

fn receive<F, T>(linkno: u8, f: F) -> Result<Option<T>>
    where F: FnOnce(&[u8]) -> Result<T>
{
    let linkidx = linkno as usize;
    unsafe {
        if (board::csr::DRTIO[linkidx].aux_rx_present_read)() == 1 {
            let ptr = board::mem::DRTIO_AUX[linkidx].base +
                      board::mem::DRTIO_AUX[linkidx].size / 2;
            let len = (board::csr::DRTIO[linkidx].aux_rx_length_read)();
            let result = f(slice::from_raw_parts(ptr as *mut u8, len as usize));
            (board::csr::DRTIO[linkidx].aux_rx_present_write)(1);
            Ok(Some(result?))
        } else {
            Ok(None)
        }
    }
}

pub fn recv_link(linkno: u8) -> Result<Option<Packet>> {
    if has_rx_error(linkno) {
        return Err(Error::GatewareError)
    }

    receive(linkno, |buffer| {
        if buffer.len() < 8 {
            return Err(Error::Io(IoError::UnexpectedEof))
        }

        let mut reader = Cursor::new(buffer);

        let checksum_at = buffer.len() - 4;
        let checksum = crc::crc32::checksum_ieee(&reader.get_ref()[0..checksum_at]);
        reader.set_position(checksum_at);
        if reader.read_u32()? != checksum {
            return Err(Error::CorruptedPacket)
        }
        reader.set_position(0);

        Ok(Packet::read_from(&mut reader)?)
    })
}

pub fn recv_timeout_link(linkno: u8, timeout_ms: Option<u64>) -> Result<Packet> {
    let timeout_ms = timeout_ms.unwrap_or(10);
    let limit = board::clock::get_ms() + timeout_ms;
    while board::clock::get_ms() < limit {
        match recv_link(linkno)? {
            None => (),
            Some(packet) => return Ok(packet),
        }
    }
    Err(Error::TimedOut)
}

fn transmit<F>(linkno: u8, f: F) -> Result<()>
    where F: FnOnce(&mut [u8]) -> Result<usize>
{
    let linkno = linkno as usize;
    unsafe {
        while (board::csr::DRTIO[linkno].aux_tx_read)() != 0 {}
        let ptr = board::mem::DRTIO_AUX[linkno].base;
        let len = board::mem::DRTIO_AUX[linkno].size / 2;
        let len = f(slice::from_raw_parts_mut(ptr as *mut u8, len))?;
        (board::csr::DRTIO[linkno].aux_tx_length_write)(len as u16);
        (board::csr::DRTIO[linkno].aux_tx_write)(1);
        Ok(())
    }
}

pub fn send_link(linkno: u8, packet: &Packet) -> Result<()> {
    transmit(linkno, |buffer| {
        let mut writer = Cursor::new(buffer);

        packet.write_to(&mut writer)?;

        let padding = 4 - (writer.position() % 4);
        if padding != 4 {
            for _ in 0..padding {
                writer.write_u8(0)?;
            }
        }

        let checksum = crc::crc32::checksum_ieee(&writer.get_ref()[0..writer.position()]);
        writer.write_u32(checksum)?;

        Ok(writer.position())
    })
}

// TODO: routing
fn get_linkno(nodeno: u8) -> Result<u8> {
    if nodeno == 0 || nodeno as usize > board::csr::DRTIO.len() {
        return Err(Error::NoRoute)
    }
    Ok(nodeno - 1)
}

pub fn recv(nodeno: u8) -> Result<Option<Packet>> {
    let linkno = get_linkno(nodeno)?;
    recv_link(linkno)
}

pub fn recv_timeout(nodeno: u8, timeout_ms: Option<u64>) -> Result<Packet> {
    let linkno = get_linkno(nodeno)?;
    recv_timeout_link(linkno, timeout_ms)
}

pub fn send(nodeno: u8, packet: &Packet) -> Result<()> {
    let linkno = get_linkno(nodeno)?;
    send_link(linkno, packet)
}
