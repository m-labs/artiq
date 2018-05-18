use core::str::Utf8Error;
use alloc::{Vec, String};

use io::{Read, ProtoRead, Write, ProtoWrite, Error as IoError, ReadStringError};

#[derive(Fail, Debug)]
pub enum Error<T> {
    #[fail(display = "incorrect magic")]
    WrongMagic,
    #[fail(display = "unknown packet {:#02x}", _0)]
    UnknownPacket(u8),
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
    const MAGIC: &'static [u8] = b"ARTIQ coredev\n";

    let mut magic: [u8; 14] = [0; 14];
    reader.read_exact(&mut magic)?;
    if magic != MAGIC {
        Err(Error::WrongMagic)
    } else {
        Ok(())
    }
}

fn read_sync<R>(reader: &mut R) -> Result<(), IoError<R::ReadError>>
    where R: Read + ?Sized
{
    let mut sync = [0; 4];
    for i in 0.. {
        sync[i % 4] = reader.read_u8()?;
        if sync == [0x5a; 4] { break }
    }
    Ok(())
}

fn write_sync<W>(writer: &mut W) -> Result<(), IoError<W::WriteError>>
    where W: Write + ?Sized
{
    writer.write_all(&[0x5a; 4])
}

#[derive(Debug)]
pub enum Request {
    SystemInfo,

    LoadKernel(Vec<u8>),
    RunKernel,

    RpcReply { tag: Vec<u8> },
    RpcException {
        name:     String,
        message:  String,
        param:    [i64; 3],
        file:     String,
        line:     u32,
        column:   u32,
        function: String,
    },
}

#[derive(Debug)]
pub enum Reply<'a> {
    SystemInfo {
        ident: &'a str,
        finished_cleanly: bool
    },

    LoadCompleted,
    LoadFailed(&'a str),

    KernelFinished,
    KernelStartupFailed,
    KernelException {
        name:      &'a str,
        message:   &'a str,
        param:     [i64; 3],
        file:      &'a str,
        line:      u32,
        column:    u32,
        function:  &'a str,
        backtrace: &'a [usize]
    },

    RpcRequest { async: bool },

    WatchdogExpired,
    ClockFailure,
}

impl Request {
    pub fn read_from<R>(reader: &mut R) -> Result<Self, Error<R::ReadError>>
        where R: Read + ?Sized
    {
        read_sync(reader)?;
        Ok(match reader.read_u8()? {
            3  => Request::SystemInfo,

            5  => Request::LoadKernel(reader.read_bytes()?),
            6  => Request::RunKernel,

            7  => Request::RpcReply {
                tag: reader.read_bytes()?
            },
            8  => Request::RpcException {
                name:     reader.read_string()?,
                message:  reader.read_string()?,
                param:    [reader.read_u64()? as i64,
                           reader.read_u64()? as i64,
                           reader.read_u64()? as i64],
                file:     reader.read_string()?,
                line:     reader.read_u32()?,
                column:   reader.read_u32()?,
                function: reader.read_string()?
            },

            ty  => return Err(Error::UnknownPacket(ty))
        })
    }
}

impl<'a> Reply<'a> {
    pub fn write_to<W>(&self, writer: &mut W) -> Result<(), IoError<W::WriteError>>
        where W: Write + ?Sized
    {
        write_sync(writer)?;
        match *self {
            Reply::SystemInfo { ident, finished_cleanly } => {
                writer.write_u8(2)?;
                writer.write(b"AROR")?;
                writer.write_string(ident)?;
                writer.write_u8(finished_cleanly as u8)?;
            },

            Reply::LoadCompleted => {
                writer.write_u8(5)?;
            },
            Reply::LoadFailed(reason) => {
                writer.write_u8(6)?;
                writer.write_string(reason)?;
            },

            Reply::KernelFinished => {
                writer.write_u8(7)?;
            },
            Reply::KernelStartupFailed => {
                writer.write_u8(8)?;
            },
            Reply::KernelException {
                name, message, param, file, line, column, function, backtrace
            } => {
                writer.write_u8(9)?;
                writer.write_string(name)?;
                writer.write_string(message)?;
                writer.write_u64(param[0] as u64)?;
                writer.write_u64(param[1] as u64)?;
                writer.write_u64(param[2] as u64)?;
                writer.write_string(file)?;
                writer.write_u32(line)?;
                writer.write_u32(column)?;
                writer.write_string(function)?;
                writer.write_u32(backtrace.len() as u32)?;
                for &addr in backtrace {
                    writer.write_u32(addr as u32)?
                }
            },

            Reply::RpcRequest { async } => {
                writer.write_u8(10)?;
                writer.write_u8(async as u8)?;
            },

            Reply::WatchdogExpired => {
                writer.write_u8(14)?;
            },
            Reply::ClockFailure => {
                writer.write_u8(15)?;
            },
        }
        Ok(())
    }
}
