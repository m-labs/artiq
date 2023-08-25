use board_misoc::{csr, clock, config};
#[cfg(feature = "alloc")]
use alloc::format;


struct SerdesConfig {
    pub delay: [u8; 4],
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

fn select_lane(lane_no: u8) {
    unsafe {
        csr::eem_transceiver::lane_sel_write(lane_no);
    }
}

fn apply_delay(tap: u8) {
    unsafe {
        csr::eem_transceiver::dly_cnt_in_write(tap);
        csr::eem_transceiver::dly_ld_write(1);
        clock::spin_us(1);
        assert!(tap as u8 == csr::eem_transceiver::dly_cnt_out_read());
    }
}

fn apply_config(config: &SerdesConfig) {
    for lane_no in 0..4 {
        select_lane(lane_no as u8);
        apply_delay(config.delay[lane_no]);
    }
}

unsafe fn assign_delay() -> SerdesConfig {
    // Select an appropriate delay for lane 0
    select_lane(0);

    let read_align = |dly: u8| -> f32 {
        apply_delay(dly);
        csr::eem_transceiver::counter_reset_write(1);

        csr::eem_transceiver::counter_enable_write(1);
        clock::spin_us(2000);
        csr::eem_transceiver::counter_enable_write(0);

        let (high, low) = (
            csr::eem_transceiver::counter_high_count_read(),
            csr::eem_transceiver::counter_low_count_read(),
        );
        if csr::eem_transceiver::counter_overflow_read() == 1 {
            panic!("Unexpected phase detector counter overflow");
        }

        low as f32 / (low + high) as f32
    };

    let mut best_dly = None;

    loop {
        let mut prev = None;
        for curr_dly in 0..32 {
            let curr_low_rate = read_align(curr_dly);

            if let Some(prev_low_rate) = prev {
                // This is potentially a crossover position
                if prev_low_rate <= curr_low_rate && curr_low_rate >= 0.5 {
                    let prev_dev = 0.5 - prev_low_rate;
                    let curr_dev = curr_low_rate - 0.5;
                    let selected_idx = if prev_dev < curr_dev {
                        curr_dly - 1
                    } else {
                        curr_dly
                    };

                    // The setup setup/hold calibration timing (even with
                    // tolerance) might be invalid in other lanes due to skew.
                    // 5 taps is very conservative, generally it is 1 or 2
                    if selected_idx < 5 {
                        prev = None;
                        continue;
                    } else {
                        best_dly = Some(selected_idx);
                        break;
                    }
                }
            }

            // Only rising slope from <= 0.5 can result in a rising low rate
            // crossover at 50%.
            if curr_low_rate <= 0.5 {
                prev = Some(curr_low_rate);
            }
        }

        if best_dly.is_none() {
            error!("setup/hold timing calibration failed, retry in 1s...");
            clock::spin_us(1_000_000);
        } else {
            break;
        }
    }

    let best_dly = best_dly.unwrap();

    apply_delay(best_dly);
    let mut delay_list = [best_dly; 4];

    // Assign delay for other lanes
    for lane_no in 1..=3 {
        select_lane(lane_no as u8);

        let mut min_deviation = 0.5;
        let mut min_idx = 0;
        for dly_delta in -3..=3 {
            let index = (best_dly as isize + dly_delta) as u8;
            let low_rate = read_align(index);
            // abs() from f32 is not available in core library
            let deviation = if low_rate < 0.5 {
                0.5 - low_rate
            } else {
                low_rate - 0.5
            };

            if deviation < min_deviation {
                min_deviation = deviation;
                min_idx = index;
            }
        }

        apply_delay(min_idx);
        delay_list[lane_no] = min_idx;
    }

    debug!("setup/hold timing calibration: {:?}", delay_list);

    SerdesConfig {
        delay: delay_list,
    }
}

unsafe fn align_comma() {
    loop {
        for slip in 1..=10 {
            // The soft transceiver has 2 8b10b decoders, which receives lane
            // 0/1 and lane 2/3 respectively. The decoder are time-multiplexed
            // to decode exactly 1 lane each sysclk cycle.
            //
            // The decoder decodes lane 0/2 data on odd sysclk cycles, buffer
            // on even cycles, and vice versa for lane 1/3. Data/Clock latency
            // could change timing. The extend bit flips the decoding timing,
            // so lane 0/2 data are decoded on even cycles, and lane 1/3 data
            // are decoded on odd cycles.
            //
            // This is needed because transmitting/receiving a 8b10b character
            // takes 2 sysclk cycles. Adjusting bitslip only via ISERDES
            // limits the range to 1 cycle. The wordslip bit extends the range
            // to 2 sysclk cycles.
            csr::eem_transceiver::wordslip_write((slip > 5) as u8);

            // Apply a double bitslip since the ISERDES is 2x oversampled.
            // Bitslip is used for comma alignment purposes once setup/hold
            // timing is met.
            csr::eem_transceiver::bitslip_write(1);
            csr::eem_transceiver::bitslip_write(1);
            clock::spin_us(1);

            csr::eem_transceiver::comma_align_reset_write(1);
            clock::spin_us(100);

            if csr::eem_transceiver::comma_read() == 1 {
                debug!("comma alignment completed after {} bitslips", slip);
                return;
            }
        }

        error!("comma alignment failed, retrying in 1s...");
        clock::spin_us(1_000_000);
    }
}

pub fn init() {
    for trx_no in 0..csr::CONFIG_EEM_DRTIO_COUNT {
        unsafe {
            csr::eem_transceiver::transceiver_sel_write(trx_no as u8);
        }

        let key = format!("eem_drtio_delay{}", trx_no);
        config::read(&key, |r| {
            match r {
                Ok(record) => {
                    info!("loading calibrated timing values from flash");
                    unsafe {
                        apply_config(&*(record.as_ptr() as *const SerdesConfig));
                    }
                },

                Err(_) => {
                    info!("calibrating...");
                    let config = unsafe { assign_delay() };
                    config::write(&key, config.as_bytes()).unwrap();
                }
            }
        });

        unsafe {
            align_comma();
            csr::eem_transceiver::rx_ready_write(1);
        }
    }
}
