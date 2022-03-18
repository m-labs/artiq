use i2c;

/// [Hardware manual](http://ww1.microchip.com/downloads/en/DeviceDoc/24AA02E48-24AA025E48-24AA02E64-24AA025E64-Data-Sheet-20002124H.pdf)
pub struct EEPROM {
    busno: u8,
    port: u8,
    address: u8,
}

impl EEPROM {
    #[cfg(all(soc_platform = "kasli", any(hw_rev = "v1.0", hw_rev = "v1.1")))]
    pub fn new() -> Self {
        EEPROM {
            busno: 0,
            /// Same port as Si5324
            port: 11,
            address: 0xa0,
        }
    }

    #[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
    pub fn new() -> Self {
        EEPROM {
            busno: 0,
            /// SHARED I2C bus
            port: 11,
            address: 0xae,
        }
    }

    #[cfg(soc_platform = "kasli")]
    fn select(&self) -> Result<(), &'static str> {
        let mask: u16 = 1 << self.port;
        i2c::switch_select(self.busno, 0x70, mask as u8)?;
        i2c::switch_select(self.busno, 0x71, (mask >> 8) as u8)?;
        Ok(())
    }

    pub fn read<'a>(&self, addr: u8, buf: &'a mut [u8]) -> Result<(), &'static str> {
        self.select()?;

        i2c::start(self.busno)?;
        i2c::write(self.busno, self.address)?;
        i2c::write(self.busno, addr)?;

        i2c::restart(self.busno)?;
        i2c::write(self.busno, self.address | 1)?;
        let buf_len = buf.len();
        for (i, byte) in buf.iter_mut().enumerate() {
            *byte = i2c::read(self.busno, i < buf_len - 1)?;
        }

        i2c::stop(self.busno)?;

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
