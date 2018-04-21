use std::vec::Vec;
use std::io::{self, Read, Write};
use {ReadExt, WriteExt};
#[cfg(feature = "log")]
use log;

#[derive(Debug)]
pub enum Request {
    GetLog,
    ClearLog,
    PullLog,
    #[cfg(feature = "log")]
    SetLogFilter(log::LevelFilter),
    #[cfg(feature = "log")]
    SetUartLogFilter(log::LevelFilter),

    Hotswap(Vec<u8>),
    Reboot,

    DebugAllocator,
}

pub enum Reply<'a> {
    Success,

    LogContent(&'a str),

    RebootImminent,
}

impl Request {
    pub fn read_from(reader: &mut Read) -> io::Result<Request> {
        #[cfg(feature = "log")]
        fn read_log_level_filter(reader: &mut Read) -> io::Result<log::LevelFilter> {
            Ok(match reader.read_u8()? {
                0 => log::LevelFilter::Off,
                1 => log::LevelFilter::Error,
                2 => log::LevelFilter::Warn,
                3 => log::LevelFilter::Info,
                4 => log::LevelFilter::Debug,
                5 => log::LevelFilter::Trace,
                _ => return Err(io::Error::new(io::ErrorKind::InvalidData,
                                               "invalid log level"))
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
            4 => Request::Hotswap(reader.read_bytes()?),
            5 => Request::Reboot,
            8 => Request::DebugAllocator,
            _  => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown request type"))
        })
    }
}

impl<'a> Reply<'a> {
    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        match *self {
            Reply::Success => {
                writer.write_u8(1)?;
            },

            Reply::LogContent(ref log) => {
                writer.write_u8(2)?;
                writer.write_string(log)?;
            },

            Reply::RebootImminent => {
                writer.write_u8(3)?;
            },
        }
        Ok(())
    }
}
