use std::io::{self, Read, Write};
use proto::*;

#[derive(Debug)]
pub enum TtlMode {
    Experiment,
    High,
    Low,
    Input
}

impl TtlMode {
    pub fn read_from(reader: &mut Read) -> io::Result<TtlMode> {
        Ok(match try!(read_u8(reader)) {
            0 => TtlMode::Experiment,
            1 => TtlMode::High,
            2 => TtlMode::Low,
            3 => TtlMode::Input,
            _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown TTL mode"))
        })
    }
}

#[derive(Debug)]
pub enum Request {
    Monitor,
    TtlSet { channel: u8, mode: TtlMode }
}

impl Request {
    pub fn read_from(reader: &mut Read) -> io::Result<Request> {
        Ok(match try!(read_u8(reader)) {
            1 => Request::Monitor,
            2 => Request::TtlSet {
                channel: try!(read_u8(reader)),
                mode: try!(TtlMode::read_from(reader))
            },
            _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown request type"))
        })
    }
}

#[derive(Debug, Default)]
pub struct Reply<'a> {
    pub ttl_levels: u64,
    pub ttl_oes: u64,
    pub ttl_overrides: u64,
    pub dds_rtio_first_channel: u16,
    pub dds_channels_per_bus: u16,
    pub dds_ftws: &'a [u32]
}

impl<'a> Reply<'a> {
    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        try!(write_u64(writer, self.ttl_levels));
        try!(write_u64(writer, self.ttl_oes));
        try!(write_u64(writer, self.ttl_overrides));
        try!(write_u16(writer, self.dds_rtio_first_channel));
        try!(write_u16(writer, self.dds_channels_per_bus));
        for dds_ftw in self.dds_ftws {
            try!(write_u32(writer, *dds_ftw));
        }
        Ok(())
    }
}
