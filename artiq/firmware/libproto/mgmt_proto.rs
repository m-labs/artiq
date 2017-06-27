use std::vec::Vec;
use std::io::{self, Read, Write};
use {ReadExt, WriteExt};
#[cfg(feature = "log")]
use log::LogLevelFilter;

#[derive(Debug)]
pub enum Request {
    GetLog,
    ClearLog,
    #[cfg(feature = "log")]
    SetLogFilter(LogLevelFilter),
    #[cfg(feature = "log")]
    SetUartLogFilter(LogLevelFilter),

    Hotswap(Vec<u8>),
    Reboot,
}

pub enum Reply<'a> {
    Success,

    LogContent(&'a str),

    RebootImminent,
}

impl Request {
    pub fn read_from(reader: &mut Read) -> io::Result<Request> {
        #[cfg(feature = "log")]
        fn read_log_level_filter(reader: &mut Read) -> io::Result<LogLevelFilter> {
            Ok(match reader.read_u8()? {
                0 => LogLevelFilter::Off,
                1 => LogLevelFilter::Error,
                2 => LogLevelFilter::Warn,
                3 => LogLevelFilter::Info,
                4 => LogLevelFilter::Debug,
                5 => LogLevelFilter::Trace,
                _ => return Err(io::Error::new(io::ErrorKind::InvalidData,
                                               "invalid log level"))
            })
        }

        Ok(match reader.read_u8()? {
            1  => Request::GetLog,
            2  => Request::ClearLog,
            #[cfg(feature = "log")]
            3 => Request::SetLogFilter(read_log_level_filter(reader)?),
            #[cfg(feature = "log")]
            6 => Request::SetUartLogFilter(read_log_level_filter(reader)?),
            4 => Request::Hotswap(reader.read_bytes()?),
            5 => Request::Reboot,
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
