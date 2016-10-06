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
pub struct Exception {
    name:     String,
    message:  String,
    param:    [u64; 3],
    file:     String,
    line:     u32,
    column:   u32,
    function: String,
}

impl Exception {
    pub fn read_from(reader: &mut Read) -> io::Result<Exception> {
        Ok(Exception {
            name:     try!(read_string(reader)),
            message:  try!(read_string(reader)),
            param:    [try!(read_u64(reader)),
                       try!(read_u64(reader)),
                       try!(read_u64(reader))],
            file:     try!(read_string(reader)),
            line:     try!(read_u32(reader)),
            column:   try!(read_u32(reader)),
            function: try!(read_string(reader))
        })
    }

    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        try!(write_string(writer, &self.name));
        try!(write_string(writer, &self.message));
        try!(write_u64(writer, self.param[0]));
        try!(write_u64(writer, self.param[1]));
        try!(write_u64(writer, self.param[2]));
        try!(write_string(writer, &self.file));
        try!(write_u32(writer, self.line));
        try!(write_u32(writer, self.column));
        try!(write_string(writer, &self.function));
        Ok(())
    }
}

#[derive(Debug)]
pub enum Request {
    Log,
    LogClear,

    Ident,
    SwitchClock(u8),

    LoadKernel(Vec<u8>),
    RunKernel,

    RpcReply { tag: Vec<u8>, data: Vec<u8> },
    RpcException(Exception),

    FlashRead   { key: String },
    FlashWrite  { key: String, value: Vec<u8> },
    FlashRemove { key: String },
    FlashErase,
}

impl Request {
    pub fn read_from(reader: &mut Read) -> io::Result<Request> {
        const HEADER_SIZE: usize = 9;

        try!(read_sync(reader));
        let length = try!(read_u32(reader)) as usize;
        let ty = try!(read_u8(reader));

        Ok(match ty {
            1  => Request::Log,
            2  => Request::LogClear,
            3  => Request::Ident,
            4  => Request::SwitchClock(try!(read_u8(reader))),
            5  => {
                let mut code = vec![0; length - HEADER_SIZE];
                try!(reader.read_exact(&mut code));
                Request::LoadKernel(code)
            }
            6  => Request::RunKernel,
            7  => {
                let tag = try!(read_bytes(reader));
                let mut data = vec![0; length - HEADER_SIZE - 4 - tag.len()];
                try!(reader.read_exact(&mut data));
                Request::RpcReply { tag: tag, data: data }
            }
            8  => Request::RpcException(try!(Exception::read_from(reader))),
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
    KernelException(Exception),

    RpcRequest { service: u32, data: &'a [u8] },

    FlashRead(&'a [u8]),
    FlashOk,
    FlashError,

    WatchdogExpired,
    ClockFailure,
}

impl<'a> Reply<'a> {
    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        let mut buf = Vec::new();
        try!(write_sync(&mut buf));
        try!(write_u32(&mut buf, 0)); // length placeholder

        match *self {
            Reply::Log(ref log) => {
                try!(write_u8(&mut buf, 1));
                try!(buf.write(log.as_bytes()));
            },

            Reply::Ident(ident) => {
                try!(write_u8(&mut buf, 2));
                try!(buf.write(b"AROR"));
                try!(buf.write(ident.as_bytes()));
            },
            Reply::ClockSwitchCompleted => {
                try!(write_u8(&mut buf, 3));
            },
            Reply::ClockSwitchFailed => {
                try!(write_u8(&mut buf, 4));
            },

            Reply::LoadCompleted => {
                try!(write_u8(&mut buf, 5));
            },
            Reply::LoadFailed => {
                try!(write_u8(&mut buf, 6));
            },

            Reply::KernelFinished => {
                try!(write_u8(&mut buf, 7));
            },
            Reply::KernelStartupFailed => {
                try!(write_u8(&mut buf, 8));
            },
            Reply::KernelException(ref exception) => {
                try!(write_u8(&mut buf, 9));
                try!(exception.write_to(writer));
            },

            Reply::RpcRequest { service, data } => {
                try!(write_u8(&mut buf, 10));
                try!(write_u32(&mut buf, service));
                try!(buf.write(data));
            },

            Reply::FlashRead(ref bytes) => {
                try!(write_u8(&mut buf, 11));
                try!(buf.write(bytes));
            },
            Reply::FlashOk => {
                try!(write_u8(&mut buf, 12));
            },
            Reply::FlashError => {
                try!(write_u8(&mut buf, 13));
            },

            Reply::WatchdogExpired => {
                try!(write_u8(&mut buf, 14));
            },
            Reply::ClockFailure => {
                try!(write_u8(&mut buf, 15));
            },
        }

        let len = buf.len();
        try!(write_u32(&mut &mut buf[4..8], len as u32));

        writer.write_all(&buf)
    }
}
