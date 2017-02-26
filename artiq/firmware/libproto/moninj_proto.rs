use std::io::{self, Read, Write};
use io::*;

#[derive(Debug)]
pub enum HostMessage {
    Monitor { enable: bool, channel: u32, probe: u8 },
    Inject { channel: u32, overrd: u8, value: u8 },
    GetInjectionStatus { channel: u32, overrd: u8 }
}

#[derive(Debug)]
pub enum DeviceMessage {
    MonitorStatus { channel: u32, probe: u8, value: u32 },
    InjectionStatus { channel: u32, overrd: u8, value: u8 }
}

impl HostMessage {
    pub fn read_from(reader: &mut Read) -> io::Result<HostMessage> {
        Ok(match read_u8(reader)? {
            0 => HostMessage::Monitor {
                enable: if read_u8(reader)? == 0 { false } else { true },
                channel: read_u32(reader)?,
                probe: read_u8(reader)?
            },
            1 => HostMessage::Inject {
                channel: read_u32(reader)?,
                overrd: read_u8(reader)?,
                value: read_u8(reader)?
            },
            2 => HostMessage::GetInjectionStatus {
                channel: read_u32(reader)?,
                overrd: read_u8(reader)?
            },
            _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown packet type"))
        })
    }
}

impl DeviceMessage {
    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        match *self {
            DeviceMessage::MonitorStatus { channel, probe, value } => {
                write_u8(writer, 0)?;
                write_u32(writer, channel)?;
                write_u8(writer, probe)?;
                write_u32(writer, value)?;
            },
            DeviceMessage::InjectionStatus { channel, overrd, value } => {
                write_u8(writer, 1)?;
                write_u32(writer, channel)?;
                write_u8(writer, overrd)?;
                write_u8(writer, value)?;
            }
        }
        Ok(())
    }
}
