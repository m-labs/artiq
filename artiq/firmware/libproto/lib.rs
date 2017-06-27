#![no_std]

extern crate byteorder;
extern crate cslice;
#[cfg(feature = "log")]
#[macro_use]
extern crate log;

extern crate dyld;
extern crate std_artiq as std;

// Internal protocols.
pub mod kernel_proto;

// External protocols.
pub mod mgmt_proto;
pub mod analyzer_proto;
pub mod moninj_proto;
pub mod session_proto;
pub mod rpc_proto;

use std::io::{Read, Write, Result, Error, ErrorKind};
use std::vec::Vec;
use std::string::String;
use byteorder::{ByteOrder, NetworkEndian};

pub trait ReadExt: Read {
    fn read_u8(&mut self) -> Result<u8> {
        let mut bytes = [0; 1];
        self.read_exact(&mut bytes)?;
        Ok(bytes[0])
    }

    fn read_u16(&mut self) -> Result<u16> {
        let mut bytes = [0; 2];
        self.read_exact(&mut bytes)?;
        Ok(NetworkEndian::read_u16(&bytes))
    }

    fn read_u32(&mut self) -> Result<u32> {
        let mut bytes = [0; 4];
        self.read_exact(&mut bytes)?;
        Ok(NetworkEndian::read_u32(&bytes))
    }

    fn read_u64(&mut self) -> Result<u64> {
        let mut bytes = [0; 8];
        self.read_exact(&mut bytes)?;
        Ok(NetworkEndian::read_u64(&bytes))
    }

    fn read_bytes(&mut self) -> Result<Vec<u8>> {
        let length = self.read_u32()?;
        let mut value = Vec::new();
        value.resize(length as usize, 0);
        self.read_exact(&mut value)?;
        Ok(value)
    }

    fn read_string(&mut self) -> Result<String> {
        let bytes = self.read_bytes()?;
        String::from_utf8(bytes)
               .map_err(|_| Error::new(ErrorKind::InvalidData, "invalid UTF-8"))
    }
}

impl<R: Read + ?Sized> ReadExt for R {}

pub trait WriteExt: Write {
    fn write_u8(&mut self, value: u8) -> Result<()> {
        let bytes = [value; 1];
        self.write_all(&bytes)
    }

    fn write_u16(&mut self, value: u16) -> Result<()> {
        let mut bytes = [0; 2];
        NetworkEndian::write_u16(&mut bytes, value);
        self.write_all(&bytes)
    }

    fn write_u32(&mut self, value: u32) -> Result<()> {
        let mut bytes = [0; 4];
        NetworkEndian::write_u32(&mut bytes, value);
        self.write_all(&bytes)
    }

    fn write_u64(&mut self, value: u64) -> Result<()> {
        let mut bytes = [0; 8];
        NetworkEndian::write_u64(&mut bytes, value);
        self.write_all(&bytes)
    }

    fn write_bytes(&mut self, value: &[u8]) -> Result<()> {
        self.write_u32(value.len() as u32)?;
        self.write_all(value)
    }

    fn write_string(&mut self, value: &str) -> Result<()> {
        self.write_bytes(value.as_bytes())
    }
}

impl<W: Write + ?Sized> WriteExt for W {}
