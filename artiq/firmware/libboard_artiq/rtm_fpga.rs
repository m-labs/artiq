use core::slice;
use board::csr::rtm_fpga_cfg;
use board::clock;

const ADDR: *const u8 = 0x150000 as *const u8;

pub fn program_bitstream() -> Result<(), ()> {
    unsafe {
        let length    = *(ADDR as *const usize);
        let bitstream = slice::from_raw_parts(ADDR.offset(4) as *const u32, length / 4);

        debug!("resetting");

        rtm_fpga_cfg::divisor_write(15);
        rtm_fpga_cfg::program_write(1);
        clock::spin_us(1000);
        rtm_fpga_cfg::program_write(0);
        clock::spin_us(1000);

        while rtm_fpga_cfg::error_read() != 0 {}

        debug!("programming");

        for word in bitstream {
            rtm_fpga_cfg::data_write(*word);
            rtm_fpga_cfg::start_write(1);
            while rtm_fpga_cfg::busy_read() == 1 {}
        }

        debug!("finishing");

        loop {
            if rtm_fpga_cfg::error_read() != 0 {
                error!("programming error");

                return Err(())
            }

            if rtm_fpga_cfg::done_read() != 0 {
                debug!("done");

                return Ok(())
            }
        }
    }
}
