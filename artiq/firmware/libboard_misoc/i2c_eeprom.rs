use i2c;

/// [Hardware manual for Kasli's 24AA02E48](http://ww1.microchip.com/downloads/en/DeviceDoc/24AA02E48-24AA025E48-24AA02E64-24AA025E64-Data-Sheet-20002124H.pdf)
/// [Hardware manual for Metlino's AT24MAC402](http://ww1.microchip.com/downloads/en/devicedoc/Atmel-8807-SEEPROM-AT24MAC402-602-Datasheet.pdf)
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

    #[cfg(soc_platform = "metlino")]
    pub fn new() -> Self {
        EEPROM {
            busno: 0,
            port: 5,
            address: 0xa2,  // == 0x51 << 1
        }
    }

    #[cfg(soc_platform = "kasli")]
    fn select(&self) -> Result<(), &'static str> {
        let mask: u16 = 1 << self.port;
        i2c::pca9548_select(self.busno, 0x70, mask as u8)?;
        i2c::pca9548_select(self.busno, 0x71, (mask >> 8) as u8)?;
        Ok(())
    }

    #[cfg(soc_platform = "metlino")]
    fn select(&self) -> Result<(), &'static str> {
        let mask: u16 = 1 << self.port;
        i2c::pca9548_select(self.busno, 0x70, mask as u8)?;     // FPGA_I2C
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

    #[cfg(soc_platform = "kasli")]
    /// > The 24AA02XEXX is programmed at the factory with a
    /// > globally unique node address stored in the upper half
    /// > of the array and permanently write-protected.
    pub fn read_eui48<'a>(&self) -> Result<[u8; 6], &'static str> {
        let mut buffer = [0u8; 6];
        self.read(0xFA, &mut buffer)?;
        Ok(buffer)
    }

    #[cfg(soc_platform = "metlino")]
    /// The AT24MAC402 requires a special EUI Address Read instruction;
    /// see Figure 12-5: EUI Address Read.
    /// For the EUI48 address, see Section 7.1 EUI-48 Support.
    pub fn read_eui48<'a>(&self) -> Result<[u8; 6], &'static str> {
        self.select()?;

        // Emit START condition
        i2c::start(self.busno)?;
        // Write 0b[1011 A2 A1 A0] as device address
        i2c::write(self.busno, 0b10110000 | (self.address & 0b1110))?;
        // Write EUI word start address
        i2c::write(self.busno, 0x9A)?;

        // Re-emit START condition
        i2c::restart(self.busno)?;
        // Write 0b[1011 A2 A1 A0] as device address
        i2c::write(self.busno, 0b10110001 | (self.address & 0b1110))?;

        // Read 6 bytes, expect NACK at the final byte
        let mut buffer = [0u8; 6];
        let buf_len = buffer.len();
        for (i, byte) in buffer.iter_mut().enumerate() {
            *byte = i2c::read(self.busno, i < buf_len - 1)?;
        }

        // Emit STOP condition
        i2c::stop(self.busno)?;

        Ok(buffer)
    }

}
