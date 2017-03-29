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

    Hotswap(Vec<u8>),
}

pub enum Reply<'a> {
    Success,

    LogContent(&'a str),

    HotswapImminent,
}

impl Request {
    pub fn read_from(reader: &mut Read) -> io::Result<Request> {
        Ok(match reader.read_u8()? {
            1  => Request::GetLog,
            2  => Request::ClearLog,
            #[cfg(feature = "log")]
            3 => {
                let level = match reader.read_u8()? {
                    0 => LogLevelFilter::Off,
                    1 => LogLevelFilter::Error,
                    2 => LogLevelFilter::Warn,
                    3 => LogLevelFilter::Info,
                    4 => LogLevelFilter::Debug,
                    5 => LogLevelFilter::Trace,
                    _ => return Err(io::Error::new(io::ErrorKind::InvalidData,
                                                   "invalid log level"))
                };
                Request::SetLogFilter(level)
            }
            4 => Request::Hotswap(reader.read_bytes()?),
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

            Reply::HotswapImminent => {
                writer.write_u8(3)?;
            },
        }
        Ok(())
    }
}
