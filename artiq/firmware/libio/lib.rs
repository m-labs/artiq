#![no_std]
#![feature(never_type)]
#![cfg_attr(feature = "alloc", feature(alloc))]

#[cfg(feature = "alloc")]
#[macro_use]
extern crate alloc;
#[cfg(feature = "byteorder")]
extern crate byteorder;

#[cfg(feature = "std_artiq")]
extern crate std_artiq;

use core::result;
use core::fmt;

#[cfg(feature = "byteorder")]
pub mod proto;

pub type Result<T, E> = result::Result<T, Error<E>>;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error<T> {
    UnexpectedEof,
    Unrecognized,
    Other(T)
}

impl<T: fmt::Display> fmt::Display for Error<T> {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            &Error::UnexpectedEof =>
                write!(f, "unexpected end of stream"),
            &Error::Unrecognized =>
                write!(f, "unrecognized input"),
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

pub trait Read {
    type ReadError;

    /// Pull some bytes from this source into the specified buffer, returning
    /// how many bytes were read.
    fn read(&mut self, buf: &mut [u8]) -> result::Result<usize, Self::ReadError>;

    /// Read the exact number of bytes required to fill `buf`.
    fn read_exact(&mut self, mut buf: &mut [u8]) -> Result<(), Self::ReadError> {
        while !buf.is_empty() {
            let read_bytes = self.read(buf)?;
            if read_bytes == 0 {
                return Err(Error::UnexpectedEof)
            }

            buf = &mut { buf }[read_bytes..];
        }

        Ok(())
    }
}

pub trait Write {
    type WriteError;
    type FlushError;

    /// Write a buffer into this object, returning how many bytes were written.
    fn write(&mut self, buf: &[u8]) -> result::Result<usize, Self::WriteError>;

    /// Flush this output stream, ensuring that all intermediately buffered contents
    /// reach their destination.
    fn flush(&mut self) -> result::Result<(), Self::FlushError>;

    /// Attempts to write an entire buffer into `self`.
    fn write_all(&mut self, mut buf: &[u8]) -> Result<(), Self::WriteError> {
        while buf.len() > 0 {
            let written_bytes = self.write(buf)?;
            if written_bytes == 0 {
                return Err(Error::UnexpectedEof)
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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CursorError {
    EndOfBuffer
}

#[derive(Debug, Clone)]
pub struct Cursor<T> {
    inner: T,
    pos:   usize
}

impl<T> Cursor<T> {
    #[inline]
    pub fn new(inner: T) -> Cursor<T> {
        Cursor { inner, pos: 0 }
    }

    #[inline]
    pub fn into_inner(self) -> T {
        self.inner
    }

    #[inline]
    pub fn get_ref(&self) -> &T {
        &self.inner
    }

    #[inline]
    pub fn get_mut(&mut self) -> &mut T {
        &mut self.inner
    }

    #[inline]
    pub fn position(&self) -> usize {
        self.pos
    }

    #[inline]
    pub fn set_position(&mut self, pos: usize) {
        self.pos = pos
    }
}

impl<T: AsRef<[u8]>> Read for Cursor<T> {
    type ReadError = !;

    fn read(&mut self, buf: &mut [u8]) -> result::Result<usize, Self::ReadError> {
        let data = &self.inner.as_ref()[self.pos..];
        let len = buf.len().min(data.len());
        buf[..len].copy_from_slice(&data[..len]);
        self.pos += len;
        Ok(len)
    }
}

impl<'a> Write for Cursor<&'a mut [u8]> {
    type WriteError = !;
    type FlushError = !;

    fn write(&mut self, buf: &[u8]) -> result::Result<usize, Self::WriteError> {
        let data = &mut self.inner[self.pos..];
        let len  = buf.len().min(data.len());
        data[..len].copy_from_slice(&buf[..len]);
        self.pos += len;
        Ok(len)
    }

    #[inline]
    fn flush(&mut self) -> result::Result<(), Self::FlushError> {
        Ok(())
    }
}

#[cfg(feature = "alloc")]
impl Write for Cursor<::alloc::Vec<u8>> {
    type WriteError = !;
    type FlushError = !;

    #[inline]
    fn write(&mut self, buf: &[u8]) -> result::Result<usize, Self::WriteError> {
        self.inner.extend(buf);
        Ok(buf.len())
    }

    #[inline]
    fn flush(&mut self) -> result::Result<(), Self::FlushError> {
        Ok(())
    }
}

#[cfg(feature = "std_artiq")]
impl<T> Read for T where T: std_artiq::io::Read + ?Sized {
    type ReadError = std_artiq::io::Error;

    fn read(&mut self, buf: &mut [u8]) -> result::Result<usize, Self::ReadError> {
        std_artiq::io::Read::read(self, buf)
    }
}

#[cfg(feature = "std_artiq")]
impl<T> Write for T where T: std_artiq::io::Write + ?Sized {
    type WriteError = std_artiq::io::Error;
    type FlushError = std_artiq::io::Error;

    fn write(&mut self, buf: &[u8]) -> result::Result<usize, Self::WriteError> {
        std_artiq::io::Write::write(self, buf)
    }

    fn flush(&mut self) -> result::Result<(), Self::WriteError> {
        std_artiq::io::Write::flush(self)
    }
}

#[cfg(feature = "std_artiq")]
impl<T> From<Error<T>> for std_artiq::io::Error
    where T: Into<std_artiq::io::Error>
{
    fn from(value: Error<T>) -> std_artiq::io::Error {
        match value {
            Error::UnexpectedEof =>
                std_artiq::io::Error::new(std_artiq::io::ErrorKind::UnexpectedEof,
                                          "unexpected end of stream"),
            Error::Unrecognized =>
                std_artiq::io::Error::new(std_artiq::io::ErrorKind::InvalidData,
                                          "unrecognized data"),
            Error::Other(err) =>
                err.into()
        }
    }
}
