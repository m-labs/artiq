use i2c;
use pca9548;

#[cfg(soc_platform = "kasli")]
const I2C_SWITCH0: u8 = 0x70;
#[cfg(soc_platform = "kasli")]
const I2C_SWITCH1: u8 = 0x71;

/// [Hardware manual](http://ww1.microchip.com/downloads/en/DeviceDoc/24AA02E48-24AA025E48-24AA02E64-24AA025E64-Data-Sheet-20002124H.pdf)
pub struct EEPROM {
    busno: u8,
    port: u8,
    address: u8,
}

impl EEPROM {
    pub fn kasli_eeprom() -> Self {
        EEPROM {
            busno: 0,
            /// Same port as Si5324
            port: 11,
            address: 0xa0,
        }
    }

    fn select(&self) -> Result<(), &'static str> {
        let mask: u16 = 1 << self.port;
        pca9548::select(self.busno, I2C_SWITCH0, mask as u8)?;
        pca9548::select(self.busno, I2C_SWITCH1, (mask >> 8) as u8)
    }

    pub fn read<'a>(&self, addr: u8, buf: &'a mut [u8]) -> Result<(), &'static str> {
        self.select()?;

        Ok(()).and_then(|()| {
            i2c::start(self.busno)?;
            i2c::write(self.busno, self.address)?;
            i2c::write(self.busno, addr)?;
            Ok(())
        }).map_err(|()| "I2C address write error")?;

        Ok(()).and_then(|()| {
            i2c::restart(self.busno)?;
            i2c::write(self.busno, self.address | 1)?;
            let buf_len = buf.len();
            for (i, byte) in buf.iter_mut().enumerate() {
                *byte = i2c::read(self.busno, i < buf_len - 1)?;
            }

            i2c::stop(self.busno)?;
            Ok(())
        }).map_err(|()| "I2C read error")?;

        Ok(())
    }

    /// > The 24AA02XEXX is programmed at the factory with a
    /// > globally unique node address stored in the upper half
    /// > of the array and permanently write-protected.
    pub fn read_eui48<'a>(&self) -> Result<[u8; 6], &'static str> {
        let mut buffer = [0u8; 6];
        self.read(0xFA, &mut buffer)?;
        Ok(buffer)
    }
}
