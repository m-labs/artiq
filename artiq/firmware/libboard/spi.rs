#[cfg(has_converter_spi)]
use csr;

#[cfg(has_converter_spi)]
pub fn set_config(busno: u8, flags: u8, write_div: u8, read_div: u8) -> Result<(), ()> {
    if busno != 0 {
        return Err(())
    }
    unsafe {
        csr::converter_spi::offline_write(1);
        csr::converter_spi::cs_polarity_write(flags >> 3 & 1);
        csr::converter_spi::clk_polarity_write(flags >> 4 & 1);
        csr::converter_spi::clk_phase_write(flags >> 5 & 1);
        csr::converter_spi::lsb_first_write(flags >> 6 & 1);
        csr::converter_spi::half_duplex_write(flags >> 7 & 1);
        csr::converter_spi::clk_div_write_write(write_div);
        csr::converter_spi::clk_div_read_write(read_div);
        csr::converter_spi::offline_write(0);
    }
    Ok(())
}

#[cfg(has_converter_spi)]
pub fn set_xfer(busno: u8, chip_select: u16, write_length: u8, read_length: u8) -> Result<(), ()> {
    if busno != 0 {
        return Err(())
    }
    unsafe {
        csr::converter_spi::cs_write(chip_select as _);
        csr::converter_spi::xfer_len_write_write(write_length);
        csr::converter_spi::xfer_len_read_write(read_length);
    }
    Ok(())
}

#[cfg(has_converter_spi)]
pub fn write(busno: u8, data: u32) -> Result<(), ()> {
    if busno != 0 {
        return Err(())
    }
    unsafe {
        csr::converter_spi::data_write_write(data);
        while csr::converter_spi::pending_read() != 0 {}
        while csr::converter_spi::active_read() != 0 {}
    }
    Ok(())
}

#[cfg(has_converter_spi)]
pub fn read(busno: u8) -> Result<u32, ()> {
    if busno != 0 {
        return Err(())
    }
    Ok(unsafe {
        csr::converter_spi::data_read_read()
    })
}

#[cfg(not(has_converter_spi))]
pub fn set_config(_busno: u8, _flags: u8, _write_div: u8, _read_div: u8) -> Result<(), ()> { Err(()) }
#[cfg(not(has_converter_spi))]
pub fn set_xfer(_busno: u8,_chip_select: u16, _write_length: u8, _read_length: u8) -> Result<(), ()> { Err(()) }
#[cfg(not(has_converter_spi))]
pub fn write(_busno: u8,_data: u32) -> Result<(), ()> { Err(()) }
#[cfg(not(has_converter_spi))]
pub fn read(_busno: u8,) -> Result<u32, ()> { Err(()) }
