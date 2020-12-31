#![no_std]
#![feature(never_type)]
#![cfg_attr(feature = "alloc", feature(alloc))]

extern crate failure;
#[macro_use]
extern crate failure_derive;
#[cfg(feature = "alloc")]
#[macro_use]
extern crate alloc;
#[cfg(feature = "byteorder")]
extern crate byteorder;

mod cursor;
#[cfg(feature = "byteorder")]
mod proto;

pub use cursor::Cursor;
#[cfg(feature = "byteorder")]
pub use proto::{ProtoRead, ProtoWrite};
#[cfg(all(feature = "byteorder", feature = "alloc"))]
pub use proto::ReadStringError;

#[derive(Fail, Debug, Clone, PartialEq)]
pub enum Error<T> {
    #[fail(display = "unexpected end of stream")]
    UnexpectedEnd,
    #[fail(display = "{}", _0)]
    Other(#[cause] T)
}

impl<T> From<T> for Error<T> {
    fn from(value: T) -> Error<T> {
        Error::Other(value)
    }
}

pub trait Read {
    type ReadError;

    /// Pull some bytes from this source into the specified buffer, returning
    /// how many bytes were read.
    fn read(&mut self, buf: &mut [u8]) -> Result<usize, Self::ReadError>;

    /// Read the exact number of bytes required to fill `buf`.
    fn read_exact(&mut self, mut buf: &mut [u8]) -> Result<(), Error<Self::ReadError>> {
        while !buf.is_empty() {
            let read_bytes = self.read(buf)?;
            if read_bytes == 0 {
                return Err(Error::UnexpectedEnd)
            }

            buf = &mut { buf }[read_bytes..];
        }

        Ok(())
    }
}

impl<'a, T: Read> Read for &'a mut T {
    type ReadError = T::ReadError;

    fn read(&mut self, buf: &mut [u8]) -> Result<usize, Self::ReadError> {
        T::read(self, buf)
    }
}

pub trait Write {
    type WriteError;
    type FlushError;

    /// Write a buffer into this object, returning how many bytes were written.
    fn write(&mut self, buf: &[u8]) -> Result<usize, Self::WriteError>;

    /// Flush this output stream, ensuring that all intermediately buffered contents
    /// reach their destination.
    fn flush(&mut self) -> Result<(), Self::FlushError>;

    /// Attempts to write an entire buffer into `self`.
    fn write_all(&mut self, mut buf: &[u8]) -> Result<(), Error<Self::WriteError>> {
        while buf.len() > 0 {
            let written_bytes = self.write(buf)?;
            if written_bytes == 0 {
                return Err(Error::UnexpectedEnd)
            }

            buf = &buf[written_bytes..];
        }

        Ok(())
    }

    /// Hints the writer how much bytes will be written after call to this function.
    ///
    /// At least `min` bytes should be written after the call to this function and
    /// if `max` is `Some(x)` than at most `x` bytes should be written.
    fn size_hint(&mut self, _min: usize, _max: Option<usize>) {}
}

impl<'a, T: Write> Write for &'a mut T {
    type WriteError = T::WriteError;
    type FlushError = T::FlushError;

    fn write(&mut self, buf: &[u8]) -> Result<usize, Self::WriteError> {
        T::write(self, buf)
    }

    fn flush(&mut self) -> Result<(), Self::FlushError> {
        T::flush(self)
    }

    fn size_hint(&mut self, min: usize, max: Option<usize>) {
        T::size_hint(self, min, max)
    }
}

impl<'a> Write for &'a mut [u8] {
    type WriteError = !;
    type FlushError = !;

    fn write(&mut self, buf: &[u8]) -> Result<usize, Self::WriteError> {
        let len = buf.len().min(self.len());
        self[..len].copy_from_slice(&buf[..len]);
        Ok(len)
    }

    #[inline]
    fn flush(&mut self) -> Result<(), Self::FlushError> {
        Ok(())
    }
}

#[cfg(feature = "alloc")]
impl<'a> Write for alloc::Vec<u8> {
    type WriteError = !;
    type FlushError = !;

    fn write(&mut self, buf: &[u8]) -> Result<usize, Self::WriteError> {
        self.extend_from_slice(buf);
        Ok(buf.len())
    }

    #[inline]
    fn flush(&mut self) -> Result<(), Self::FlushError> {
        Ok(())
    }
}
