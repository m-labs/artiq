use core::str::Utf8Error;
use alloc::{Vec, String};
#[cfg(feature = "log")]
use log;

use io::{Read, ProtoRead, Write, ProtoWrite, Error as IoError, ReadStringError};

#[derive(Fail, Debug)]
pub enum Error<T> {
    #[fail(display = "incorrect magic")]
    WrongMagic,
    #[fail(display = "unknown packet {:#02x}", _0)]
    UnknownPacket(u8),
    #[fail(display = "unknown log level {}", _0)]
    UnknownLogLevel(u8),
    #[fail(display = "invalid UTF-8: {}", _0)]
    Utf8(Utf8Error),
    #[fail(display = "{}", _0)]
    Io(#[cause] IoError<T>)
}

impl<T> From<IoError<T>> for Error<T> {
    fn from(value: IoError<T>) -> Error<T> {
        Error::Io(value)
    }
}

impl<T> From<ReadStringError<IoError<T>>> for Error<T> {
    fn from(value: ReadStringError<IoError<T>>) -> Error<T> {
        match value {
            ReadStringError::Utf8(err) => Error::Utf8(err),
            ReadStringError::Other(err) => Error::Io(err)
        }
    }
}

pub fn read_magic<R>(reader: &mut R) -> Result<(), Error<R::ReadError>>
    where R: Read + ?Sized
{
    const MAGIC: &'static [u8] = b"ARTIQ management\n";

    let mut magic: [u8; 17] = [0; 17];
    reader.read_exact(&mut magic)?;
    if magic != MAGIC {
        Err(Error::WrongMagic)
    } else {
        Ok(())
    }
}

#[derive(Debug)]
pub enum Request {
    GetLog,
    ClearLog,
    PullLog,
    #[cfg(feature = "log")]
    SetLogFilter(log::LevelFilter),
    #[cfg(feature = "log")]
    SetUartLogFilter(log::LevelFilter),

    ConfigRead   { key: String },
    ConfigWrite  { key: String, value: Vec<u8> },
    ConfigRemove { key: String },
    ConfigErase,

    StartProfiler {
        interval_us: u32,
        hits_size: u32,
        edges_size: u32,
    },
    StopProfiler,
    GetProfile,

    Hotswap(Vec<u8>),
    Reboot,

    DebugAllocator,
}

pub enum Reply<'a> {
    Success,
    Error,
    Unavailable,

    LogContent(&'a str),

    ConfigData(&'a [u8]),

    Profile,

    RebootImminent,
}

impl Request {
    pub fn read_from<R>(reader: &mut R) -> Result<Self, Error<R::ReadError>>
        where R: Read + ?Sized
    {
        #[cfg(feature = "log")]
        fn read_log_level_filter<T: Read + ?Sized>(reader: &mut T) ->
                Result<log::LevelFilter, Error<T::ReadError>> {
            Ok(match reader.read_u8()? {
                0 => log::LevelFilter::Off,
                1 => log::LevelFilter::Error,
                2 => log::LevelFilter::Warn,
                3 => log::LevelFilter::Info,
                4 => log::LevelFilter::Debug,
                5 => log::LevelFilter::Trace,
                lv => return Err(Error::UnknownLogLevel(lv))
            })
        }

        Ok(match reader.read_u8()? {
            1  => Request::GetLog,
            2  => Request::ClearLog,
            7  => Request::PullLog,
            #[cfg(feature = "log")]
            3 => Request::SetLogFilter(read_log_level_filter(reader)?),
            #[cfg(feature = "log")]
            6 => Request::SetUartLogFilter(read_log_level_filter(reader)?),

            12 => Request::ConfigRead {
                key: reader.read_string()?
            },
            13 => Request::ConfigWrite {
                key:   reader.read_string()?,
                value: reader.read_bytes()?
            },
            14 => Request::ConfigRemove {
                key: reader.read_string()?
            },
            15 => Request::ConfigErase,

            9 => Request::StartProfiler {
                interval_us: reader.read_u32()?,
                hits_size: reader.read_u32()?,
                edges_size: reader.read_u32()?,
            },
            10 => Request::StopProfiler,
            11 => Request::GetProfile,

            4 => Request::Hotswap(reader.read_bytes()?),
            5 => Request::Reboot,

            8 => Request::DebugAllocator,

            ty => return Err(Error::UnknownPacket(ty))
        })
    }
}

impl<'a> Reply<'a> {
    pub fn write_to<W>(&self, writer: &mut W) -> Result<(), IoError<W::WriteError>>
        where W: Write + ?Sized
    {
        match *self {
            Reply::Success => {
                writer.write_u8(1)?;
            }
            Reply::Error => {
                writer.write_u8(6)?;
            }

            Reply::Unavailable => {
                writer.write_u8(4)?;
            }

            Reply::LogContent(ref log) => {
                writer.write_u8(2)?;
                writer.write_string(log)?;
            }

            Reply::ConfigData(ref bytes) => {
                writer.write_u8(7)?;
                writer.write_bytes(bytes)?;
            },

            Reply::Profile => {
                writer.write_u8(5)?;
                // profile data follows
            }

            Reply::RebootImminent => {
                writer.write_u8(3)?;
            }
        }
        Ok(())
    }
}
