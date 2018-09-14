use core::slice;
use crc;

use io::{ProtoRead, ProtoWrite, Cursor, Error as IoError};
use board_misoc::{csr::DRTIOAUX, mem::DRTIOAUX_MEM, clock};
use proto_artiq::drtioaux_proto::Error as ProtocolError;

pub use proto_artiq::drtioaux_proto::Packet;

// this is parametric over T because there's no impl Fail for !.
#[derive(Fail, Debug)]
pub enum Error<T> {
    #[fail(display = "gateware reported error")]
    GatewareError,
    #[fail(display = "packet CRC failed")]
    CorruptedPacket,

    #[fail(display = "link is down")]
    LinkDown,
    #[fail(display = "timed out waiting for data")]
    TimedOut,
    #[fail(display = "unexpected reply")]
    UnexpectedReply,

    #[fail(display = "routing error")]
    RoutingError,

    #[fail(display = "protocol error: {}", _0)]
    Protocol(#[cause] ProtocolError<T>)
}

impl<T> From<ProtocolError<T>> for Error<T> {
    fn from(value: ProtocolError<T>) -> Error<T> {
        Error::Protocol(value)
    }
}

impl<T> From<IoError<T>> for Error<T> {
    fn from(value: IoError<T>) -> Error<T> {
        Error::Protocol(ProtocolError::Io(value))
    }
}

pub fn reset(linkno: u8) {
    let linkno = linkno as usize;
    unsafe {
        // clear buffer first to limit race window with buffer overflow
        // error. We assume the CPU is fast enough so that no two packets
        // will be received between the buffer and the error flag are cleared.
        (DRTIOAUX[linkno].aux_rx_present_write)(1);
        (DRTIOAUX[linkno].aux_rx_error_write)(1);
    }
}

fn has_rx_error(linkno: u8) -> bool {
    let linkno = linkno as usize;
    unsafe {
        let error = (DRTIOAUX[linkno].aux_rx_error_read)() != 0;
        if error {
            (DRTIOAUX[linkno].aux_rx_error_write)(1)
        }
        error
    }
}

fn receive<F, T>(linkno: u8, f: F) -> Result<Option<T>, Error<!>>
    where F: FnOnce(&[u8]) -> Result<T, Error<!>>
{
    let linkidx = linkno as usize;
    unsafe {
        if (DRTIOAUX[linkidx].aux_rx_present_read)() == 1 {
            let ptr = DRTIOAUX_MEM[linkidx].base + DRTIOAUX_MEM[linkidx].size / 2;
            let len = (DRTIOAUX[linkidx].aux_rx_length_read)();
            let result = f(slice::from_raw_parts(ptr as *mut u8, len as usize));
            (DRTIOAUX[linkidx].aux_rx_present_write)(1);
            Ok(Some(result?))
        } else {
            Ok(None)
        }
    }
}

pub fn recv(linkno: u8) -> Result<Option<Packet>, Error<!>> {
    if has_rx_error(linkno) {
        return Err(Error::GatewareError)
    }

    receive(linkno, |buffer| {
        if buffer.len() < 8 {
            return Err(IoError::UnexpectedEnd.into())
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

pub fn recv_timeout(linkno: u8, timeout_ms: Option<u64>) -> Result<Packet, Error<!>> {
    let timeout_ms = timeout_ms.unwrap_or(10);
    let limit = clock::get_ms() + timeout_ms;
    while clock::get_ms() < limit {
        match recv(linkno)? {
            None => (),
            Some(packet) => return Ok(packet),
        }
    }
    Err(Error::TimedOut)
}

fn transmit<F>(linkno: u8, f: F) -> Result<(), Error<!>>
    where F: FnOnce(&mut [u8]) -> Result<usize, Error<!>>
{
    let linkno = linkno as usize;
    unsafe {
        while (DRTIOAUX[linkno].aux_tx_read)() != 0 {}
        let ptr = DRTIOAUX_MEM[linkno].base;
        let len = DRTIOAUX_MEM[linkno].size / 2;
        let len = f(slice::from_raw_parts_mut(ptr as *mut u8, len))?;
        (DRTIOAUX[linkno].aux_tx_length_write)(len as u16);
        (DRTIOAUX[linkno].aux_tx_write)(1);
        Ok(())
    }
}

pub fn send(linkno: u8, packet: &Packet) -> Result<(), Error<!>> {
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
