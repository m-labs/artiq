use i2c;
use csr;

pub struct IoExpander {
    busno: u8,
    port: u8,
    address: u8,
    virtual_led_mapping: &'static [(u8, u8, u8)],
    iodir: [u8; 2],
    out_current: [u8; 2],
    out_target: [u8; 2],
}

impl IoExpander {
    #[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
    pub fn new(index: u8) -> Self {
        const VIRTUAL_LED_MAPPING0: [(u8, u8, u8); 2] = [(0, 0, 6), (1, 1, 6)];
        const VIRTUAL_LED_MAPPING1: [(u8, u8, u8); 2] = [(2, 0, 6), (3, 1, 6)];
        // Both expanders on SHARED I2C bus
        match index {
            0 => IoExpander {
                busno: 0,
                port: 11,
                address: 0x40,
                virtual_led_mapping: &VIRTUAL_LED_MAPPING0,
                iodir: [0xff; 2],
                out_current: [0; 2],
                out_target: [0; 2],
            },
            1 => IoExpander {
                busno: 0,
                port: 11,
                address: 0x42,
                virtual_led_mapping: &VIRTUAL_LED_MAPPING1,
                iodir: [0xff; 2],
                out_current: [0; 2],
                out_target: [0; 2],
            },
            _ => panic!("incorrect I/O expander index"),
        }
    }

    #[cfg(soc_platform = "kasli")]
    fn select(&self) -> Result<(), &'static str> {
        let mask: u16 = 1 << self.port;
        i2c::switch_select(self.busno, 0x70, mask as u8)?;
        i2c::switch_select(self.busno, 0x71, (mask >> 8) as u8)?;
        Ok(())
    }

    fn write(&self, addr: u8, value: u8) -> Result<(), &'static str> {
        i2c::start(self.busno)?;
        i2c::write(self.busno, self.address)?;
        i2c::write(self.busno, addr)?;
        i2c::write(self.busno, value)?;
        i2c::stop(self.busno)?;
        Ok(())
    }

    fn update_iodir(&self) -> Result<(), &'static str> {
        self.write(0x00, self.iodir[0])?;
        self.write(0x01, self.iodir[1])?;
        Ok(())
    }

    pub fn init(&mut self) -> Result<(), &'static str> {
        self.select()?;

        for (_led, port, bit) in self.virtual_led_mapping.iter() {
            self.iodir[*port as usize] &= !(1 << *bit);
        }
        self.update_iodir()?;

        self.out_current[0] = 0x00;
        self.write(0x12, 0x00)?;
        self.out_current[1] = 0x00;
        self.write(0x13, 0x00)?;
        Ok(())
    }

    pub fn set_oe(&mut self, port: u8, outputs: u8) -> Result<(), &'static str> {
        self.iodir[port as usize] &= !outputs;
        self.update_iodir()?;
        Ok(())
    }

    pub fn set(&mut self, port: u8, bit: u8, high: bool) {
        if high {
            self.out_target[port as usize] |= 1 << bit;
        } else {
            self.out_target[port as usize] &= !(1 << bit);
        }
    }

    pub fn service(&mut self) -> Result<(), &'static str> {
        for (led, port, bit) in self.virtual_led_mapping.iter() {
            let level = unsafe {
                (csr::virtual_leds::status_read() >> led) & 1
            };
            self.set(*port, *bit, level != 0);
        }

        if self.out_target != self.out_current {
            self.select()?;
            if self.out_target[0] != self.out_current[0] {
                self.write(0x12, self.out_target[0])?;
                self.out_current[0] = self.out_target[0];
            }
            if self.out_target[1] != self.out_current[1] {
                self.write(0x13, self.out_target[1])?;
                self.out_current[1] = self.out_target[1];
            }
        }

        Ok(())
    }
}
