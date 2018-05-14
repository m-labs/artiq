#[cfg(feature = "alloc")]
use core::fmt;
#[cfg(feature = "alloc")]
use alloc::string;
use byteorder::{ByteOrder, NetworkEndian};

use ::{Read, Write, Error as IoError};

#[cfg(feature = "alloc")]
#[derive(Debug)]
pub enum ReadStringError<T> {
    Utf8Error(string::FromUtf8Error),
    Other(T)
}

#[cfg(feature = "alloc")]
impl<T: fmt::Display> fmt::Display for ReadStringError<T> {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            &ReadStringError::Utf8Error(ref err) =>
                write!(f, "invalid UTF-8 ({})", err),
            &ReadStringError::Other(ref err) =>
                write!(f, "{}", err)
        }
    }
}

#[cfg(feature = "alloc")]
impl<T> From<ReadStringError<IoError<T>>> for IoError<T>
{
    fn from(value: ReadStringError<IoError<T>>) -> IoError<T> {
        match value {
            ReadStringError::Utf8Error(_) => IoError::Unrecognized,
            ReadStringError::Other(err) => err
        }
    }
}

#[cfg(feature = "alloc")]
#[cfg(feature = "std_artiq")]
impl<T> From<ReadStringError<T>> for ::std_artiq::io::Error
        where T: Into<::std_artiq::io::Error>
{
    fn from(value: ReadStringError<T>) -> ::std_artiq::io::Error {
        match value {
            ReadStringError::Utf8Error(_) =>
                ::std_artiq::io::Error::new(::std_artiq::io::ErrorKind::InvalidData,
                                            "invalid UTF-8"),
            ReadStringError::Other(err) => err.into()
        }
    }
}

pub trait ProtoRead {
    type ReadError;

    fn read_exact(&mut self, buf: &mut [u8]) -> Result<(), Self::ReadError>;

    #[inline]
    fn read_u8(&mut self) -> Result<u8, Self::ReadError> {
        let mut bytes = [0; 1];
        self.read_exact(&mut bytes)?;
        Ok(bytes[0])
    }

    #[inline]
    fn read_u16(&mut self) -> Result<u16, Self::ReadError> {
        let mut bytes = [0; 2];
        self.read_exact(&mut bytes)?;
        Ok(NetworkEndian::read_u16(&bytes))
    }

    #[inline]
    fn read_u32(&mut self) -> Result<u32, Self::ReadError> {
        let mut bytes = [0; 4];
        self.read_exact(&mut bytes)?;
        Ok(NetworkEndian::read_u32(&bytes))
    }

    #[inline]
    fn read_u64(&mut self) -> Result<u64, Self::ReadError> {
        let mut bytes = [0; 8];
        self.read_exact(&mut bytes)?;
        Ok(NetworkEndian::read_u64(&bytes))
    }

    #[inline]
    fn read_bool(&mut self) -> Result<bool, Self::ReadError> {
        Ok(self.read_u8()? != 0)
    }

    #[cfg(feature = "alloc")]
    #[inline]
    fn read_bytes(&mut self) -> Result<::alloc::Vec<u8>, Self::ReadError> {
        let length = self.read_u32()?;
        let mut value = vec![0; length as usize];
        self.read_exact(&mut value)?;
        Ok(value)
    }

    #[cfg(feature = "alloc")]
    #[inline]
    fn read_string(&mut self) -> Result<::alloc::String, ReadStringError<Self::ReadError>> {
        match self.read_bytes() {
            Ok(bytes) =>
                match ::alloc::String::from_utf8(bytes) {
                    Ok(string) => Ok(string),
                    Err(err) => Err(ReadStringError::Utf8Error(err))
                },
            Err(err) => Err(ReadStringError::Other(err))
        }
    }
}

pub trait ProtoWrite {
    type WriteError;

    fn write_all(&mut self, buf: &[u8]) -> Result<(), Self::WriteError>;

    #[inline]
    fn write_u8(&mut self, value: u8) -> Result<(), Self::WriteError> {
        let bytes = [value; 1];
        self.write_all(&bytes)
    }

    #[inline]
    fn write_i8(&mut self, value: i8) -> Result<(), Self::WriteError> {
        let bytes = [value as u8; 1];
        self.write_all(&bytes)
    }

    #[inline]
    fn write_u16(&mut self, value: u16) -> Result<(), Self::WriteError> {
        let mut bytes = [0; 2];
        NetworkEndian::write_u16(&mut bytes, value);
        self.write_all(&bytes)
    }

    #[inline]
    fn write_i16(&mut self, value: i16) -> Result<(), Self::WriteError> {
        let mut bytes = [0; 2];
        NetworkEndian::write_i16(&mut bytes, value);
        self.write_all(&bytes)
    }

    #[inline]
    fn write_u32(&mut self, value: u32) -> Result<(), Self::WriteError> {
        let mut bytes = [0; 4];
        NetworkEndian::write_u32(&mut bytes, value);
        self.write_all(&bytes)
    }

    #[inline]
    fn write_i32(&mut self, value: i32) -> Result<(), Self::WriteError> {
        let mut bytes = [0; 4];
        NetworkEndian::write_i32(&mut bytes, value);
        self.write_all(&bytes)
    }

    #[inline]
    fn write_u64(&mut self, value: u64) -> Result<(), Self::WriteError> {
        let mut bytes = [0; 8];
        NetworkEndian::write_u64(&mut bytes, value);
        self.write_all(&bytes)
    }

    #[inline]
    fn write_i64(&mut self, value: i64) -> Result<(), Self::WriteError> {
        let mut bytes = [0; 8];
        NetworkEndian::write_i64(&mut bytes, value);
        self.write_all(&bytes)
    }

    #[inline]
    fn write_bool(&mut self, value: bool) -> Result<(), Self::WriteError> {
        self.write_u8(value as u8)
    }

    #[inline]
    fn write_bytes(&mut self, value: &[u8]) -> Result<(), Self::WriteError> {
        self.write_u32(value.len() as u32)?;
        self.write_all(value)
    }

    #[inline]
    fn write_string(&mut self, value: &str) -> Result<(), Self::WriteError> {
        self.write_bytes(value.as_bytes())
    }
}

impl<T> ProtoRead for T where T: Read + ?Sized {
    type ReadError = IoError<T::ReadError>;

    fn read_exact(&mut self, buf: &mut [u8]) -> Result<(), Self::ReadError> {
        T::read_exact(self, buf)
    }
}

impl<T> ProtoWrite for T where T: Write + ?Sized {
    type WriteError = IoError<T::WriteError>;

    fn write_all(&mut self, buf: &[u8]) -> Result<(), Self::WriteError> {
        T::write_all(self, buf)
    }
}
