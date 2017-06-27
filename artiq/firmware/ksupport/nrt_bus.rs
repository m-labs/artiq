pub mod i2c {
    use ::send;
    use ::recv;
    use kernel_proto::*;

    pub extern fn start(busno: i32) {
        send(&I2cStartRequest { busno: busno as u32 });
        recv!(&I2cBasicReply { succeeded } => if !succeeded {
            raise!("I2CError", "I2C bus could not be accessed");
        });
    }

    pub extern fn restart(busno: i32) {
        send(&I2cRestartRequest { busno: busno as u32 });
        recv!(&I2cBasicReply { succeeded } => if !succeeded {
            raise!("I2CError", "I2C bus could not be accessed");
        });
    }

    pub extern fn stop(busno: i32) {
        send(&I2cStopRequest { busno: busno as u32 });
        recv!(&I2cBasicReply { succeeded } => if !succeeded {
            raise!("I2CError", "I2C bus could not be accessed");
        });
    }

    pub extern fn write(busno: i32, data: i32) -> bool {
        send(&I2cWriteRequest { busno: busno as u32, data: data as u8 });
        recv!(&I2cWriteReply { succeeded, ack } => {
            if !succeeded {
                raise!("I2CError", "I2C bus could not be accessed");
            }
            ack
        })
    }

    pub extern fn read(busno: i32, ack: bool) -> i32 {
        send(&I2cReadRequest { busno: busno as u32, ack: ack });
        recv!(&I2cReadReply { succeeded, data } => {
            if !succeeded {
                raise!("I2CError", "I2C bus could not be accessed");
            }
            data
        }) as i32
    }
}

pub mod spi {
    use ::send;
    use ::recv;
    use kernel_proto::*;

    pub extern fn set_config(busno: i32, flags: i32, write_div: i32, read_div: i32) {
        send(&SpiSetConfigRequest { busno: busno as u32, flags: flags as u8,
                                    write_div: write_div as u8, read_div: read_div as u8 });
        recv!(&SpiBasicReply { succeeded } => if !succeeded {
            raise!("SPIError", "SPI bus could not be accessed");
        });
    }

    pub extern fn set_xfer(busno: i32, chip_select: i32, write_length: i32, read_length: i32) {
        send(&SpiSetXferRequest { busno: busno as u32, chip_select: chip_select as u16,
                                  write_length: write_length as u8, read_length: read_length as u8 });
        recv!(&SpiBasicReply { succeeded } => if !succeeded {
            raise!("SPIError", "SPI bus could not be accessed");
        });
    }

    pub extern fn write(busno: i32, data: i32) {
        send(&SpiWriteRequest { busno: busno as u32, data: data as u32 });
        recv!(&SpiBasicReply { succeeded } => if !succeeded {
            raise!("SPIError", "SPI bus could not be accessed");
        });
    }

    pub extern fn read(busno: i32) -> i32 {
        send(&SpiReadRequest { busno: busno as u32 });
        recv!(&SpiReadReply { succeeded, data } => {
            if !succeeded {
                raise!("SPIError", "SPI bus could not be accessed");
            }
            data
        }) as i32
    }
}
