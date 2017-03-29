use std::io::{self, Read, Write};
use std::vec::Vec;
use std::string::String;
use {ReadExt, WriteExt};

fn read_sync(reader: &mut Read) -> io::Result<()> {
    let mut sync = [0; 4];
    for i in 0.. {
        sync[i % 4] = reader.read_u8()?;
        if sync == [0x5a; 4] { break }
    }
    Ok(())
}

fn write_sync(writer: &mut Write) -> io::Result<()> {
    writer.write_all(&[0x5a; 4])
}

#[derive(Debug)]
pub enum Request {
    SystemInfo,
    SwitchClock(u8),

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

    FlashRead   { key: String },
    FlashWrite  { key: String, value: Vec<u8> },
    FlashRemove { key: String },
    FlashErase,
}

impl Request {
    pub fn read_from(reader: &mut Read) -> io::Result<Request> {
        read_sync(reader)?;
        Ok(match reader.read_u8()? {
            3  => Request::SystemInfo,
            4  => Request::SwitchClock(reader.read_u8()?),
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
            9  => Request::FlashRead {
                key: reader.read_string()?
            },
            10 => Request::FlashWrite {
                key:   reader.read_string()?,
                value: reader.read_bytes()?
            },
            11 => Request::FlashErase,
            12 => Request::FlashRemove {
                key: reader.read_string()?
            },
            _  => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown request type"))
        })
    }
}

#[derive(Debug)]
pub enum Reply<'a> {
    SystemInfo {
        ident: &'a str,
        finished_cleanly: bool
    },
    ClockSwitchCompleted,
    ClockSwitchFailed,

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

    FlashRead(&'a [u8]),
    FlashOk,
    FlashError,

    WatchdogExpired,
    ClockFailure,
}

impl<'a> Reply<'a> {
    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        write_sync(writer)?;
        match *self {
            Reply::SystemInfo { ident, finished_cleanly } => {
                writer.write_u8(2)?;
                writer.write(b"AROR")?;
                writer.write_string(ident)?;
                writer.write_u8(finished_cleanly as u8)?;
            },
            Reply::ClockSwitchCompleted => {
                writer.write_u8(3)?;
            },
            Reply::ClockSwitchFailed => {
                writer.write_u8(4)?;
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

            Reply::FlashRead(ref bytes) => {
                writer.write_u8(11)?;
                writer.write_bytes(bytes)?;
            },
            Reply::FlashOk => {
                writer.write_u8(12)?;
            },
            Reply::FlashError => {
                writer.write_u8(13)?;
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
