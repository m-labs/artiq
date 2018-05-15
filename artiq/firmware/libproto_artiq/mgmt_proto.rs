use alloc::Vec;
#[cfg(feature = "log")]
use log;

use io::{Read, ProtoRead, Write, ProtoWrite, Error};

#[derive(Debug)]
pub enum Request {
    GetLog,
    ClearLog,
    PullLog,
    #[cfg(feature = "log")]
    SetLogFilter(log::LevelFilter),
    #[cfg(feature = "log")]
    SetUartLogFilter(log::LevelFilter),

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
    Unavailable,

    LogContent(&'a str),

    Profile,

    RebootImminent,
}

impl Request {
    pub fn read_from<T: Read + ?Sized>(reader: &mut T) -> Result<Self, Error<T::ReadError>> {
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
                _ => return Err(Error::Unrecognized)
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
            _  => return Err(Error::Unrecognized)
        })
    }
}

impl<'a> Reply<'a> {
    pub fn write_to<T: Write + ?Sized>(&self, writer: &mut T) -> Result<(), Error<T::WriteError>> {
        match *self {
            Reply::Success => {
                writer.write_u8(1)?;
            }

            Reply::Unavailable => {
                writer.write_u8(4)?;
            }

            Reply::LogContent(ref log) => {
                writer.write_u8(2)?;
                writer.write_string(log)?;
            }

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
