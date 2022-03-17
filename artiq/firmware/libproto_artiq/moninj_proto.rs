use io::{Read, ProtoRead, Write, ProtoWrite, Error as IoError};

#[derive(Fail, Debug)]
pub enum Error<T> {
    #[fail(display = "incorrect magic")]
    WrongMagic,
    #[fail(display = "unknown packet {:#02x}", _0)]
    UnknownPacket(u8),
    #[fail(display = "{}", _0)]
    Io(#[cause] IoError<T>)
}

impl<T> From<IoError<T>> for Error<T> {
    fn from(value: IoError<T>) -> Error<T> {
        Error::Io(value)
    }
}

pub fn read_magic<R>(reader: &mut R) -> Result<(), Error<R::ReadError>>
    where R: Read + ?Sized
{
    const MAGIC: &'static [u8] = b"ARTIQ moninj\n";

    let mut magic: [u8; 13] = [0; 13];
    reader.read_exact(&mut magic)?;
    if magic != MAGIC {
        Err(Error::WrongMagic)
    } else {
        Ok(())
    }
}

#[derive(Debug)]
pub enum HostMessage {
    MonitorProbe { enable: bool, channel: u32, probe: u8 },
    MonitorInjection { enable: bool, channel: u32, overrd: u8 },
    Inject { channel: u32, overrd: u8, value: u8 },
    GetInjectionStatus { channel: u32, overrd: u8 }
}

#[derive(Debug)]
pub enum DeviceMessage {
    MonitorStatus { channel: u32, probe: u8, value: u32 },
    InjectionStatus { channel: u32, overrd: u8, value: u8 }
}

impl HostMessage {
    pub fn read_from<R>(reader: &mut R) -> Result<Self, Error<R::ReadError>>
        where R: Read + ?Sized
    {
        Ok(match reader.read_u8()? {
            0 => HostMessage::MonitorProbe {
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
            3 => HostMessage::MonitorInjection {
                enable: if reader.read_u8()? == 0 { false } else { true },
                channel: reader.read_u32()?,
                overrd: reader.read_u8()?
            },
            ty => return Err(Error::UnknownPacket(ty))
        })
    }
}

impl DeviceMessage {
    pub fn write_to<W>(&self, writer: &mut W) -> Result<(), IoError<W::WriteError>>
        where W: Write + ?Sized
    {
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
