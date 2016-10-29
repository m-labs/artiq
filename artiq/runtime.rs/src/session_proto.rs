use std::prelude::v1::*;
use std::io::{self, Read, Write};
use proto::*;

fn read_sync(reader: &mut Read) -> io::Result<()> {
    let mut sync = [0; 4];
    for i in 0.. {
        sync[i % 4] = try!(read_u8(reader));
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

    Ident,
    SwitchClock(u8),

    LoadKernel(Vec<u8>),
    RunKernel,

    RpcReply { tag: Vec<u8> },
    RpcException {
        name:     String,
        message:  String,
        param:    [u64; 3],
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
        try!(read_sync(reader));
        Ok(match try!(read_u8(reader)) {
            1  => Request::Log,
            2  => Request::LogClear,
            3  => Request::Ident,
            4  => Request::SwitchClock(try!(read_u8(reader))),
            5  => Request::LoadKernel(try!(read_bytes(reader))),
            6  => Request::RunKernel,
            7  => Request::RpcReply {
                tag: try!(read_bytes(reader))
            },
            8  => Request::RpcException {
                name:     try!(read_string(reader)),
                message:  try!(read_string(reader)),
                param:    [try!(read_u64(reader)),
                           try!(read_u64(reader)),
                           try!(read_u64(reader))],
                file:     try!(read_string(reader)),
                line:     try!(read_u32(reader)),
                column:   try!(read_u32(reader)),
                function: try!(read_string(reader))
            },
            9  => Request::FlashRead {
                key: try!(read_string(reader))
            },
            10 => Request::FlashWrite {
                key:   try!(read_string(reader)),
                value: try!(read_bytes(reader))
            },
            11 => Request::FlashErase,
            12 => Request::FlashRemove {
                key: try!(read_string(reader))
            },
            _  => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown request type"))
        })
    }
}

#[derive(Debug)]
pub enum Reply<'a> {
    Log(&'a str),

    Ident(&'a str),
    ClockSwitchCompleted,
    ClockSwitchFailed,

    LoadCompleted,
    LoadFailed,

    KernelFinished,
    KernelStartupFailed,
    KernelException {
        name:      &'a str,
        message:   &'a str,
        param:     [u64; 3],
        file:      &'a str,
        line:      u32,
        column:    u32,
        function:  &'a str,
        backtrace: &'a [usize]
    },

    RpcRequest,

    FlashRead(&'a [u8]),
    FlashOk,
    FlashError,

    WatchdogExpired,
    ClockFailure,
}

impl<'a> Reply<'a> {
    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        try!(write_sync(writer));
        match *self {
            Reply::Log(ref log) => {
                try!(write_u8(writer, 1));
                try!(write_string(writer, log));
            },

            Reply::Ident(ident) => {
                try!(write_u8(writer, 2));
                try!(writer.write(b"AROR"));
                try!(write_string(writer, ident));
            },
            Reply::ClockSwitchCompleted => {
                try!(write_u8(writer, 3));
            },
            Reply::ClockSwitchFailed => {
                try!(write_u8(writer, 4));
            },

            Reply::LoadCompleted => {
                try!(write_u8(writer, 5));
            },
            Reply::LoadFailed => {
                try!(write_u8(writer, 6));
            },

            Reply::KernelFinished => {
                try!(write_u8(writer, 7));
            },
            Reply::KernelStartupFailed => {
                try!(write_u8(writer, 8));
            },
            Reply::KernelException {
                name, message, param, file, line, column, function, backtrace
            } => {
                try!(write_u8(writer, 9));
                try!(write_string(writer, name));
                try!(write_string(writer, message));
                try!(write_u64(writer, param[0]));
                try!(write_u64(writer, param[1]));
                try!(write_u64(writer, param[2]));
                try!(write_string(writer, file));
                try!(write_u32(writer, line));
                try!(write_u32(writer, column));
                try!(write_string(writer, function));
                try!(write_u32(writer, backtrace.len() as u32));
                for &addr in backtrace {
                    try!(write_u32(writer, addr as u32))
                }
            },

            Reply::RpcRequest => {
                try!(write_u8(writer, 10));
            },

            Reply::FlashRead(ref bytes) => {
                try!(write_u8(writer, 11));
                try!(write_bytes(writer, bytes));
            },
            Reply::FlashOk => {
                try!(write_u8(writer, 12));
            },
            Reply::FlashError => {
                try!(write_u8(writer, 13));
            },

            Reply::WatchdogExpired => {
                try!(write_u8(writer, 14));
            },
            Reply::ClockFailure => {
                try!(write_u8(writer, 15));
            },
        }
        Ok(())
    }
}
