use board_misoc::{csr, ident, clock, uart_logger, i2c, pmp};


#[derive(Debug)]
pub struct SerdesConfig {
    select_odd: u8,
    decoder_invert: u8,
    delay: [u8; 4],
    bitslip: [u8; 4],
}

impl SerdesConfig {
    pub fn as_bytes(&self) -> &[u8] {
        unsafe {
            core::slice::from_raw_parts(
                (self as *const SerdesConfig) as *const u8,
                core::mem::size_of::<SerdesConfig>(),
            )
        }
    }
}

pub fn align_eem() -> SerdesConfig {
    let mut delay_confs: [(u8, u8, u8, u8); 4] = Default::default();

    for eem_pair_no in 0..4 {
        delay_confs[eem_pair_no] = unsafe { align(eem_pair_no) };
    }

    let mut select_odd = 0;
    let mut decoder_invert = 0;
    let mut delay = [0; 4];
    let mut bitslip = [0; 4];
    for (eem_pair_no, (select_odd_idx, dly, slip, invert)) in delay_confs.iter().enumerate() {
        select_odd |= (select_odd_idx << eem_pair_no);
        delay[eem_pair_no] = *dly;
        bitslip[eem_pair_no] = *slip;
        decoder_invert |= (invert << eem_pair_no);
    }

    SerdesConfig {
        select_odd,
        decoder_invert,
        delay,
        bitslip,
    }
}

fn select_eem_pair(eem_pair_no: usize) {
    unsafe {
        csr::eem_transceiver::serdes_bitslip_sel_write(1 << eem_pair_no);
        csr::eem_transceiver::serdes_dly_cnt_in_sel_write(1 << eem_pair_no);
        csr::eem_transceiver::serdes_dly_cnt_out_sel_write(1 << eem_pair_no);
        csr::eem_transceiver::serdes_read_word_write(eem_pair_no as u8);
    }
}

fn update_select_odd(eem_pair_no: usize, select_odd: usize) {
    let mut odd_sel_reg = unsafe { csr::eem_transceiver::serdes_select_odd_read() };
    // Clear bit
    odd_sel_reg &= (!(1 << eem_pair_no));
    // Set bit if applicable
    unsafe { csr::eem_transceiver::serdes_select_odd_write(odd_sel_reg | (select_odd << eem_pair_no) as u8) };
}

fn update_invert(eem_pair_no: usize, invert: usize) {
    let mut invert_reg = unsafe { csr::eem_transceiver::serdes_decoder_dly_read() };
    // Clear bit
    invert_reg &= (!(1 << eem_pair_no));
    // Set bit if applicable
    unsafe { csr::eem_transceiver::serdes_decoder_dly_write(invert_reg | (invert << eem_pair_no) as u8) };
}

fn apply_bitslip() {
    unsafe {
        csr::eem_transceiver::serdes_bitslip_write(1);
        csr::eem_transceiver::serdes_bitslip_write(1);
    }
}

fn apply_delay(tap: u8) {
    unsafe {
        csr::eem_transceiver::serdes_dly_cnt_in_write(tap);
        // Ensure dly_cnt_in is updated before ld
        clock::spin_us(100);
        assert!(tap == csr::eem_transceiver::serdes_dly_cnt_in_read());
        csr::eem_transceiver::serdes_dly_ld_write(1);
    }
}

pub fn write_config(config: &SerdesConfig) {
    unsafe {
        csr::eem_transceiver::serdes_decoder_dly_write(config.decoder_invert as u8);
        csr::eem_transceiver::serdes_select_odd_write(config.select_odd as u8);
    }

    for eem_pair_no in 0..4 {
        select_eem_pair(eem_pair_no);
        apply_delay(config.delay[eem_pair_no]);

        for _ in 0..config.bitslip[eem_pair_no] {
            apply_bitslip();
        }
    }
}

unsafe fn align(eem_pair_no: usize) -> (u8, u8, u8, u8) {
    let mut table: [[bool; 32]; 20] = [[false; 32]; 20];

    select_eem_pair(eem_pair_no);
    clock::spin_us(1);

    let scan = |table: &mut[[bool; 32]]| {
        for slip in 0..5 {
            for delay in 0..32 {
                apply_delay(delay);
                clock::spin_us(1);

                for odd_select in 0..2 {
                    update_select_odd(eem_pair_no, odd_select);
                    clock::spin_us(100);

                    table[(slip * 2 + odd_select) as usize][delay as usize] = true;
                    for _ in 0..512 {
                        let aligned = csr::eem_transceiver::serdes_aligned_read();
                        table[(slip * 2 + odd_select) as usize][delay as usize] &= (aligned == 1);
                    }
                }
            }

            apply_bitslip();
            clock::spin_us(100);
        }
    };

    update_invert(eem_pair_no, 0);
    clock::spin_us(100);
    scan(&mut table[..10]);
    update_invert(eem_pair_no, 1);
    clock::spin_us(100);
    scan(&mut table[10..]);

    print!("                       ");
    for i in 0..32 {
        print!("{}", i % 10);
    }
    println!("");

    for (idx, dly_row) in table.iter().enumerate() {
        let slip = (idx % 10) / 2;
        let select_odd = idx % 2;
        print!("Slip {:#02}, SELECT_ODD {}: ", slip, select_odd);
        for &hit_status in dly_row {
            if hit_status {
                print!("*");
            } else {
                print!(" ");
            }
        }
        println!("");
    }

    get_delay(&table)
}

// Find the appropriate delay configuration, in (select_odd, delay_tap, bitslip, flip_order)
fn get_delay(table: &[[bool; 32]]) -> (u8, u8, u8, u8) {
    // Figure out the longest chain of hits within some bitslip & select_odd
    let mut max = 0;
    let mut slip = 0;
    let mut tap = 0;
    for (curr_idx, dly_row) in table.iter().enumerate() {
        let mut curr_len = 0;
        let mut first_hit = 0;
        let mut curr_mid = 0;

        for (dly_tap, dly_stat) in dly_row.iter().enumerate() {
            if *dly_stat {
                // Beginning of a chain of hits
                if curr_len == 0 {
                    first_hit = dly_tap;
                }
                curr_len += 1;
                curr_mid = (dly_tap + first_hit) / 2;
            } else {
                curr_len = 0;
            }

            if curr_len > max {
                max = curr_len;
                slip = curr_idx;
                tap = curr_mid;
            }
        }
    }

    (slip as u8 % 2, tap as u8, (slip as u8 % 10) / 2, slip as u8 / 10)
}
