/*
This SPI Core is designed to replicate the equivalent behaviour of the SPI2 Core in misoc.

Configuration Flags
* :Bit 0:`spi_offline`: all pins high-z (reset=1)
* :Bit 1:`spi_end`: Transfer in progress (reset=1)
* :Bit 2:`spi_input`: (Not Supported)
* :Bit 3:`spi_cs_polarity`: active level of ``cs_n`` (reset=0)
* :Bit 4:`spi_clk_polarity`: idle level of ``clk`` (reset=0)
* :Bit 5:`spi_clk_phase`: first edge after ``cs`` assertion to sample
    data on (reset=0). In Motorola/Freescale SPI language
    (:const:`SPI_CLK_POLARITY`, :const:`SPI_CLK_PHASE`) == (CPOL, CPHA):
    - (0, 0): idle low, output on falling, input on rising
    - (0, 1): idle low, output on rising, input on falling
    - (1, 0): idle high, output on rising, input on falling
    - (1, 1): idle high, output on falling, input on rising
* :Bit 6:`spi_lsb_first`: LSB is the first bit on the wire (reset=0)
* :Bit 7:`spi_half_duplex`: 3-wire SPI, in/out on ``mosi`` (reset=0)

Extra Setting
* length: Number of bits being write or read in one transaction (reset=32)
*/

#[derive(Copy, Clone)]
pub struct Flags {
    pub spi_offline: bool,
    pub spi_end: bool,
    pub spi_cs_polarity: bool,
    pub spi_clk_polarity: bool,
    pub spi_clk_phase: bool,
    pub spi_lsb_first: bool,
    pub spi_half_duplex: bool,
}

#[cfg(has_spi)]
mod imp {
    use spi::Flags;
    use board_misoc::{csr, clock};

    const INVALID_BUS: &'static str = "Invalid SPI bus";

    #[derive(Copy, Clone)]
    struct Core {
        flags: Flags,
        length: u8,
        setup_before_write: bool,
        data_in: u32,
    }
    static mut SPI: [ Core; csr::CONFIG_SPI_BUS_COUNT as usize ] = [ Core {
        flags: Flags {
            spi_offline: false,
            spi_end: true,
            spi_cs_polarity: false,
            spi_clk_polarity: false,
            spi_clk_phase: false,
            spi_lsb_first: false,
            spi_half_duplex: false,
        },
        length: 32,
        setup_before_write: true,
        data_in: 0,
    }; csr::CONFIG_SPI_BUS_COUNT as usize];

    fn half_period() { clock::spin_us(100)}
    fn miso_bit(busno: u8) -> u8 { 1 << (4 * busno + 3) }
    fn mosi_bit(busno: u8) -> u8 { 1 << (4 * busno + 2) }
    fn sclk_bit(busno: u8) -> u8 { 1 << (4 * busno + 1) }
    fn cs_n_bit(busno: u8) -> u8 { 1 << (4 * busno) }

    fn miso_i(busno: u8) -> bool {
        unsafe {
            csr::spi::in_read() & miso_bit(busno) != 0
        }
    }

    fn mosi_i(busno: u8) -> bool {
        unsafe {
            csr::spi::in_read() & mosi_bit(busno) != 0
        }
    }

    fn sclk_i(busno: u8) -> bool {
        unsafe {
            csr::spi::in_read() & sclk_bit(busno) != 0
        }
    }

    fn cs_n_i(busno: u8) -> bool {
        unsafe {
            csr::spi::in_read() & cs_n_bit(busno) != 0
        }
    }

    fn miso_oe(busno: u8, oe: bool) {
        unsafe {
            let reg = csr::spi::oe_read();
            let reg = if oe { reg | miso_bit(busno) } else { reg & !miso_bit(busno) };
            csr::spi::oe_write(reg)
        }
    }

    fn miso_o(busno: u8, o: bool) {
        unsafe {
            let reg = csr::spi::out_read();
            let reg = if o  { reg | miso_bit(busno) } else { reg & !miso_bit(busno) };
            csr::spi::out_write(reg)
        }
    }

    fn mosi_oe(busno: u8, oe: bool) {
        unsafe {
            let reg = csr::spi::oe_read();
            let reg = if oe { reg | mosi_bit(busno) } else { reg & !mosi_bit(busno) };
            csr::spi::oe_write(reg)
        }
    }

    fn mosi_o(busno: u8, o: bool) {
        unsafe {
            let reg = csr::spi::out_read();
            let reg = if o  { reg | mosi_bit(busno) } else { reg & !mosi_bit(busno) };
            csr::spi::out_write(reg)
        }
    }

    fn sclk_oe(busno: u8, oe: bool) {
        unsafe {
            let reg = csr::spi::oe_read();
            let reg = if oe { reg | sclk_bit(busno) } else { reg & !sclk_bit(busno) };
            csr::spi::oe_write(reg)
        }
    }

    fn sclk_o(busno: u8, o: bool) {
        unsafe {
            let reg = csr::spi::out_read();
            let reg = if o  { reg | sclk_bit(busno) } else { reg & !sclk_bit(busno) };
            csr::spi::out_write(reg)
        }
    }

    fn cs_n_oe(busno: u8, oe: bool) {
        unsafe {
            let reg = csr::spi::oe_read();
            let reg = if oe { reg | cs_n_bit(busno) } else { reg & !cs_n_bit(busno) };
            csr::spi::oe_write(reg)
        }
    }

    fn cs_n_o(busno: u8, o: bool) {
        unsafe {
            let reg = csr::spi::out_read();
            let reg = if o  { reg | cs_n_bit(busno) } else { reg & !cs_n_bit(busno) };
            csr::spi::out_write(reg)
        }
    }

    fn get_spi_offline_flag(busno: u8) -> bool {
        unsafe {
            SPI[busno as usize].flags.spi_offline
        }
    }

    fn get_spi_end_flag(busno: u8) -> bool {
        unsafe {
            SPI[busno as usize].flags.spi_end
        }
    }

    fn get_spi_cs_polarity_flag(busno: u8) -> bool {
        unsafe {
            SPI[busno as usize].flags.spi_cs_polarity
        }
    }

    fn get_spi_clk_polarity_flag(busno: u8) -> bool {
        unsafe {
            SPI[busno as usize].flags.spi_clk_polarity
        }
    }

    fn get_spi_clk_phase_flag(busno: u8) -> bool {
        unsafe {
            SPI[busno as usize].flags.spi_clk_phase
        }
    }

    fn get_spi_lsb_first_flag(busno: u8) -> bool {
        unsafe {
            SPI[busno as usize].flags.spi_lsb_first
        }
    }

    fn get_spi_half_duplex_flag(busno: u8) -> bool {
        unsafe {
            SPI[busno as usize].flags.spi_half_duplex
        }
    }

    fn set_setup_before_write(busno: u8, setup_before_write: bool) {
        unsafe {
            SPI[busno as usize].setup_before_write = setup_before_write
        }
    }

    fn get_setup_before_write(busno: u8) -> bool {
        unsafe {
            SPI[busno as usize].setup_before_write
        }
    }

    fn get_length_config(busno: u8) -> u8 {
        unsafe {
            SPI[busno as usize].length
        }
    }

    fn set_data_in(busno: u8, data_in: u32) {
        unsafe {
            SPI[busno as usize].data_in = data_in
        }
    }

    fn get_data_in(busno: u8) -> u32 {
        unsafe {
            SPI[busno as usize].data_in
        }
    }

    fn setup(busno: u8) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_SPI_BUS_COUNT {
            return Err(INVALID_BUS);
        }

        mosi_o(busno, false);
        sclk_o(busno, get_spi_clk_polarity_flag(busno));
        cs_n_o(busno, !get_spi_cs_polarity_flag(busno));

        cs_n_oe(busno, !get_spi_offline_flag(busno));
        sclk_oe(busno, !get_spi_offline_flag(busno));
        mosi_oe(busno, !(get_spi_offline_flag(busno) | get_spi_half_duplex_flag(busno)));
        miso_oe(busno, false);
        
        Ok(())
    }

    fn data_inout(busno: u8, pdo: u32, mut pdi: u32, bit: u8, sdi_fn: fn(u8, bool), sdo_fn: fn(u8) -> bool) -> u32 {
        
        half_period();

        if !get_spi_clk_phase_flag(busno) {
            sdi_fn(busno, !(pdo & (1 << bit) == 0));
        }

        sclk_o(busno, !get_spi_clk_polarity_flag(busno));
        if sdo_fn(busno) {  
            pdi |= 1 << bit;
        }    
        
        half_period();

        if get_spi_clk_phase_flag(busno) {
            sdi_fn(busno, !pdo & (1 << bit) == 0);
        }
        sclk_o(busno, get_spi_clk_polarity_flag(busno));
        

        pdi
    }

    pub fn init(busno: u8) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_SPI_BUS_COUNT {
            return Err(INVALID_BUS);
        }

        cs_n_o(busno, true);
        cs_n_oe(busno, true);
        if !cs_n_i(busno) { 
            return Err("CS_N cannot be driven high"); 
        }

        cs_n_o(busno, false);
        if cs_n_i(busno) { 
            return Err("CS_N cannot be driven low"); 
        }

        sclk_o(busno, true);
        sclk_oe(busno, true);
        if !sclk_i(busno) { 
            return Err("SCLK cannot be driven high"); 
        }

        sclk_o(busno, false);
        if sclk_i(busno) { 
            return Err("SCLK cannot be driven low"); 
        }

        mosi_o(busno, true);
        mosi_oe(busno, true);
        if !mosi_i(busno) { 
            return Err("MOSI cannot be driven high"); 
        }

        mosi_o(busno, false);
        if mosi_i(busno) {
            return Err("MOSI cannot be driven low"); 
        }

        
        if !get_spi_half_duplex_flag(busno) {
            miso_o(busno, true);
            miso_oe(busno, true);
            if !miso_i(busno) {
                return Err("MISO cannot be driven high"); 
            }

            miso_o(busno, false);
            if miso_i(busno) {
                return Err("MISO cannot be driven low"); 
            }
        }
        

        setup(busno)?;

        Ok(())
    }

    pub fn set_config(busno: u8, flags: Flags, length: u8) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_SPI_BUS_COUNT {
            return Err(INVALID_BUS);
        }

        unsafe {
            SPI[busno as usize] = Core {
                flags : flags,
                length: length,
                setup_before_write: SPI[busno as usize].setup_before_write,
                data_in: SPI[busno as usize].data_in,
            };

            cs_n_oe(busno, !SPI[busno as usize].flags.spi_offline);
            sclk_oe(busno, !SPI[busno as usize].flags.spi_offline);
            mosi_oe(busno, !(SPI[busno as usize].flags.spi_offline | SPI[busno as usize].flags.spi_half_duplex));
            miso_oe(busno, false);
        }

        Ok(())
    }

    pub fn write(busno: u8, data: u32) -> Result<(), &'static str> {
        if busno as u32 >= csr::CONFIG_SPI_BUS_COUNT {
            return Err(INVALID_BUS);
        }

        if get_spi_offline_flag(busno) {
            return Err("SPI Interface is offline");
        }

        let sdi_fn: fn(u8, bool)  = mosi_o;
        let sdo_fn: fn(u8) -> bool = if get_spi_half_duplex_flag(busno) { mosi_i } else { miso_i };

        // Clear data_in at each transaction
        set_data_in(busno, 0);
        
        // Parallel data out (to serial)
        let mut pdo: u32 = data;
        // Parallel data in (from serial)
        let mut pdi: u32 = 0;

        if get_setup_before_write(busno) {
            setup(busno)?;
        
            // Assert CS_N
            cs_n_o(busno, get_spi_cs_polarity_flag(busno));
            
            half_period();
            half_period();
        }

        if get_spi_half_duplex_flag(busno) {
            mosi_oe(busno, false);
        }

        // Dummy half cycle after asserting CS in CPHA=1
        if get_spi_clk_phase_flag(busno) {
            // Output the first bit onto the mosi line
            if get_spi_lsb_first_flag(busno) {
                sdi_fn(busno, !(pdo & (1 << (0)) == 0));
                pdo = pdo >> 1;
            } else {
                sdi_fn(busno, !(pdo & (1 << (get_length_config(busno) - 1)) == 0));
                pdo = pdo << 1;
            }

            half_period();
        }
        
        // Shift the rest of the data out onto mosi
        if get_spi_lsb_first_flag(busno) {
            for bit in 0..get_length_config(busno) {
                pdi = data_inout(busno, pdo, pdi, bit, sdi_fn, sdo_fn);
            }
        } else {
            for bit in (0..get_length_config(busno)).rev() {
                pdi = data_inout(busno, pdo, pdi, bit, sdi_fn, sdo_fn);
            }
        }

        set_data_in(busno, pdi);
        
        if !get_spi_end_flag(busno) {
            set_setup_before_write(busno, true);
            
            return Ok(());
        }

        // Dummy half cycle before deasserting CS in CPHA=0
        if !get_spi_clk_phase_flag(busno) {
            sclk_o(busno, !get_spi_clk_polarity_flag(busno));
        }
        
        half_period();

        // Deassert CS_N and setup the interface for idling
        setup(busno)?;
        set_setup_before_write(busno, true);
        

        Ok(())
    }

    pub fn read(busno: u8) -> Result<u32, &'static str> {
        if busno as u32 >= csr::CONFIG_SPI_BUS_COUNT {
            return Err(INVALID_BUS);
        }
        
        Ok(get_data_in(busno))
    }
}

#[cfg(not(has_spi))]
mod imp {
    use spi::Flags;
    const NO_SPI: &'static str = "No SPI support on this platform";
    pub fn init(_busno:u8 ) -> Result<(), &'static str> { Err(NO_SPI) }
    pub fn set_config(_busno: u8, _flags: Flags, _length: u8) -> Result<(), &'static str> { Err(NO_SPI) } 
    pub fn write(_busno: u8, _data:u32) -> Result<(), &'static str> { Err(NO_SPI) }
    pub fn read(_busno: u8) -> Result<u32, &'static str> { Err(NO_SPI) }
}

pub use self::imp::*;
