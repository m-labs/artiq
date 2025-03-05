pub enum Error {
    NoSPI,
    InvalidBus,
    OtherError,
}


#[cfg(has_converter_spi)]
mod imp {
    use board_misoc::csr;
    use super::Error;

    pub fn set_config(busno: u8, flags: u8, length: u8, div: u8, cs: u8) -> Result<(), Error> {
        if busno != 0 {
            return Err(Error::InvalidBus)
        }
        unsafe {
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::offline_write(flags >> 0 & 1);
            csr::converter_spi::end_write(flags >> 1 & 1);
            // input (in RTIO): flags >> 2 & 1
            // cs_polarity is a mask in the CSR interface
            // only affect the bits that are selected
            let mut cs_polarity = csr::converter_spi::cs_polarity_read();
            if flags >> 3 & 1 != 0 {
                cs_polarity |= cs;
            } else {
                cs_polarity &= !cs;
            }
            csr::converter_spi::cs_polarity_write(cs_polarity);
            csr::converter_spi::clk_polarity_write(flags >> 4 & 1);
            csr::converter_spi::clk_phase_write(flags >> 5 & 1);
            csr::converter_spi::lsb_first_write(flags >> 6 & 1);
            csr::converter_spi::half_duplex_write(flags >> 7 & 1);
            csr::converter_spi::length_write(length - 1);
            csr::converter_spi::div_write(div - 2);
            csr::converter_spi::cs_write(cs);
        }
        Ok(())
    }

    pub fn write(busno: u8, data: u32) -> Result<(), Error> {
        if busno != 0 {
            return Err(Error::InvalidBus)
        }
        unsafe {
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::data_write(data);
        }
        Ok(())
    }

    pub fn read(busno: u8) -> Result<u32, Error> {
        if busno != 0 {
            return Err(Error::InvalidBus)
        }
        Ok(unsafe {
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::data_read()
        })
    }
}

#[cfg(not(has_converter_spi))]
mod imp {
    use super::Error;

    pub fn set_config(_busno: u8, _flags: u8, _length: u8, _div: u8, _cs: u8) -> Result<(), Error> { Err(Error::NoSPI) }
    pub fn write(_busno: u8,_data: u32) -> Result<(), Error> { Err(Error::NoSPI) }
    pub fn read(_busno: u8,) -> Result<u32, Error> { Err(Error::NoSPI) }
}

pub use self::imp::*;
