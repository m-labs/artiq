use std::io::{self, Read, Write};
use {ReadExt, WriteExt};

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
        Ok(match reader.read_u8()? {
            0 => HostMessage::Monitor {
                enable: if reader.read_u8()? == 0 { false } else { true },
                channel: reader.read_u32()?,
                probe: reader.read_u8()?
            },
            1 => HostMessage::Inject {
                channel: reader.read_u32()?,
                overrd: reader.read_u8()?,
                value: reader.read_u8()?
            },
            2 => HostMessage::GetInjectionStatus {
                channel: reader.read_u32()?,
                overrd: reader.read_u8()?
            },
            _ => return Err(io::Error::new(io::ErrorKind::InvalidData, "unknown packet type"))
        })
    }
}

impl DeviceMessage {
    pub fn write_to(&self, writer: &mut Write) -> io::Result<()> {
        match *self {
            DeviceMessage::MonitorStatus { channel, probe, value } => {
                writer.write_u8(0)?;
                writer.write_u32(channel)?;
                writer.write_u8(probe)?;
                writer.write_u32(value)?;
            },
            DeviceMessage::InjectionStatus { channel, overrd, value } => {
                writer.write_u8(1)?;
                writer.write_u32(channel)?;
                writer.write_u8(overrd)?;
                writer.write_u8(value)?;
            }
        }
        Ok(())
    }
}
