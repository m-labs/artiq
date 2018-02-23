#[cfg(has_converter_spi)]
mod imp {
    use board::csr;

    pub fn set_config(busno: u8, flags: u8, length: u8, div: u8, cs: u8) -> Result<(), ()> {
        if busno != 0 {
            return Err(())
        }
        unsafe {
            while csr::converter_spi::idle_read() == 0 {}
            csr::converter_spi::offline_write(flags >> 0 & 1);
            csr::converter_spi::end_write(flags >> 1 & 1);
            /* input (in RTIO): flags >> 2 & 1 */
            /* cs_polarity is a mask in the CSR interface */
            csr::converter_spi::cs_polarity_write(0xff & (flags >> 3 & 1));
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

    pub fn write(busno: u8, data: u32) -> Result<(), ()> {
        if busno != 0 {
            return Err(())
        }
        unsafe {
            while csr::converter_spi::writable_read() == 0 {}
            csr::converter_spi::data_write(data);
            while csr::converter_spi::writable_read() == 0 {}
        }
        Ok(())
    }

    pub fn read(busno: u8) -> Result<u32, ()> {
        if busno != 0 {
            return Err(())
        }
        Ok(unsafe {
            csr::converter_spi::data_read()
        })
    }
}

#[cfg(not(has_converter_spi))]
mod imp {
    pub fn set_config(_busno: u8, _flags: u8, _length: u8, _div: u8, _cs: u8) -> Result<(), ()> { Err(()) }
    pub fn write(_busno: u8,_data: u32) -> Result<(), ()> { Err(()) }
    pub fn read(_busno: u8,) -> Result<u32, ()> { Err(()) }
}

pub use self::imp::*;
