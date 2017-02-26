use std::io::{self, Read, Write};
use std::vec::Vec;
use std::string::String;
use io::*;

fn read_sync(reader: &mut Read) -> io::Result<()> {
    let mut sync = [0; 4];
    for i in 0.. {
        sync[i % 4] = read_u8(reader)?;
        if sync == [0x5a; 4] { break }
    }
    Ok(())
}

fn write_sync(writer: &mut Write) -> io::Result<()> {
    writer.write_all(&[0x5a; 4])
}

#[derive(Debug)]
pub enum Request {
    Log,
    LogClear,

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
        Ok(match read_u8(reader)? {
            1  => Request::Log,
            2  => Request::LogClear,
            3  => Request::SystemInfo,
            4  => Request::SwitchClock(read_u8(reader)?),
            5  => Request::LoadKernel(read_bytes(reader)?),
            6  => Request::RunKernel,
            7  => Request::RpcReply {
                tag: read_bytes(reader)?
            },
            8  => Request::RpcException {
                name:     read_string(reader)?,
                message:  read_string(reader)?,
                param:    [read_u64(reader)? as i64,
                           read_u64(reader)? as i64,
                           read_u64(reader)? as i64],
                file:     read_string(reader)?,
                line:     read_u32(reader)?,
                column:   read_u32(reader)?,
                function: read_string(reader)?
            },
            9  => Request::FlashRead {
                key: read_string(reader)?
            },
            10 => Request::FlashWrite {
                key:   read_string(reader)?,
                value: read_bytes(reader)?
            },
            11 => Request::FlashErase,
            12 => Request::FlashRemove {
                key: read_string(reader)?
            },
            _  => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown request type"))
        })
    }
}

#[derive(Debug)]
pub enum Reply<'a> {
    Log(&'a str),

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
            Reply::Log(ref log) => {
                write_u8(writer, 1)?;
                write_string(writer, log)?;
            },

            Reply::SystemInfo { ident, finished_cleanly } => {
                write_u8(writer, 2)?;
                writer.write(b"AROR")?;
                write_string(writer, ident)?;
                write_u8(writer, finished_cleanly as u8)?;
            },
            Reply::ClockSwitchCompleted => {
                write_u8(writer, 3)?;
            },
            Reply::ClockSwitchFailed => {
                write_u8(writer, 4)?;
            },

            Reply::LoadCompleted => {
                write_u8(writer, 5)?;
            },
            Reply::LoadFailed(reason) => {
                write_u8(writer, 6)?;
                write_string(writer, reason)?;
            },

            Reply::KernelFinished => {
                write_u8(writer, 7)?;
            },
            Reply::KernelStartupFailed => {
                write_u8(writer, 8)?;
            },
            Reply::KernelException {
                name, message, param, file, line, column, function, backtrace
            } => {
                write_u8(writer, 9)?;
                write_string(writer, name)?;
                write_string(writer, message)?;
                write_u64(writer, param[0] as u64)?;
                write_u64(writer, param[1] as u64)?;
                write_u64(writer, param[2] as u64)?;
                write_string(writer, file)?;
                write_u32(writer, line)?;
                write_u32(writer, column)?;
                write_string(writer, function)?;
                write_u32(writer, backtrace.len() as u32)?;
                for &addr in backtrace {
                    write_u32(writer, addr as u32)?
                }
            },

            Reply::RpcRequest { async } => {
                write_u8(writer, 10)?;
                write_u8(writer, async as u8)?;
            },

            Reply::FlashRead(ref bytes) => {
                write_u8(writer, 11)?;
                write_bytes(writer, bytes)?;
            },
            Reply::FlashOk => {
                write_u8(writer, 12)?;
            },
            Reply::FlashError => {
                write_u8(writer, 13)?;
            },

            Reply::WatchdogExpired => {
                write_u8(writer, 14)?;
            },
            Reply::ClockFailure => {
                write_u8(writer, 15)?;
            },
        }
        Ok(())
    }
}
