use board_misoc::{csr, clock, config};


struct SerdesConfig {
    pub delay: [usize; 4],
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

fn select_eem_pair(eem_pair_no: usize) {
    unsafe {
        csr::eem_transceiver::serdes_eem_sel_write(eem_pair_no as u8);
    }
}

fn apply_bitslip(extend: bool) {
    // The decoder decodes EEM 0/2 data on odd sysclk cycles, buffer on even
    // cycles, and vice versa for EEM 1/3. Data/Clock latency could change
    // timing. The invert bit flips the decoding timing, so EEM 0/2 data are
    // decoded on even cycles, and EEM 1/3 data are decoded on odd cycles.
    //
    // This is needed because transmitting/receiving a 8b10b character takes
    // 2 sysclk cycles. Adjusting bitslip only via ISERDES limits the range
    // to 1 cycle. The wordslip bit extends the range to 2 sysclk cycles.
    unsafe {
        csr::eem_transceiver::serdes_wordslip_write(extend as u8);

        // Apply a double bitslip since the ISERDES is 2x oversampled.
        // Bitslip is used for comma alignment purposes once setup/hold timing
        // is met.
        csr::eem_transceiver::serdes_bitslip_write(1);
        csr::eem_transceiver::serdes_bitslip_write(1);
    }
}

fn apply_delay(tap: usize) {
    unsafe {
        csr::eem_transceiver::serdes_dly_cnt_in_write(tap as u8);
        csr::eem_transceiver::serdes_dly_ld_write(1);
        clock::spin_us(1);
        assert!(tap as u8 == csr::eem_transceiver::serdes_dly_cnt_out_read());
    }
}

fn apply_config(config: &SerdesConfig) {
    for eem_pair_no in 0..4 {
        select_eem_pair(eem_pair_no);
        apply_delay(config.delay[eem_pair_no]);
    }
}

unsafe fn assign_delay() -> SerdesConfig {
    // Select an appropriate delay for EEM lane 0
    select_eem_pair(0);

    let read_align = |dly: usize| -> Option<f32> {
        apply_delay(dly);
        csr::eem_transceiver::serdes_counter_reset_write(1);

        csr::eem_transceiver::serdes_counter_enable_write(1);
        clock::spin_us(5000);
        csr::eem_transceiver::serdes_counter_enable_write(0);

        let (high, low) = (
            csr::eem_transceiver::serdes_counter_high_count_read(),
            csr::eem_transceiver::serdes_counter_low_count_read(),
        );
        let overflow = csr::eem_transceiver::serdes_counter_overflow_read();

        if overflow == 1 {
            None
        } else {
            Some(low as f32 / (low + high) as f32)
        }
    };

    let mut best_dly = None;
    let mut prev = None;
    for curr_dly in 0..32 {
        if let Some(curr_low_rate) = read_align(curr_dly) {
            if let Some(prev_low_rate) = prev {
                if prev_low_rate <= curr_low_rate && curr_low_rate >= 0.5 {
                    let prev_dev = 0.5 - prev_low_rate;
                    let curr_dev = curr_low_rate - 0.5;
                    let selected_idx = if prev_dev < curr_dev {
                        curr_dly - 1
                    } else {
                        curr_dly
                    };

                    // The same edge may not appear in other lanes due to skew
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

            if curr_low_rate <= 0.5 {
                prev = Some(curr_low_rate);
            }
        } else {
            prev = None;
        }
    }

    let best_dly = best_dly.expect("No suitable delay tap alignment!");

    apply_delay(best_dly);
    let mut delay_list = [best_dly; 4];

    // Assign delay for other lanes
    for lane_no in 1..=3 {
        select_eem_pair(lane_no);

        let mut min_deviation = 0.5;
        let mut min_idx = 0;
        for dly_delta in -3..=3 {
            let index = (best_dly as isize + dly_delta) as usize;
            if let Some(low_rate) = read_align(index) {
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
        }

        apply_delay(min_idx);
        delay_list[lane_no] = min_idx;
    }

    debug!("DRTIO-over-EEM calibration: {:?}", delay_list);

    SerdesConfig {
        delay: delay_list,
    }
}

unsafe fn assign_bitslip() {
    for slip in 1..=10 {
        apply_bitslip(slip > 5);
        clock::spin_us(100);

        csr::eem_transceiver::serdes_reader_reset_write(1);
        clock::spin_us(100);

        if csr::eem_transceiver::serdes_reader_comma_read() == 1 {
            debug!("Apply {} double bitslips", slip);
            break;
        } else if slip == 10 {
            panic!("No suitable bitslip found!")
        }
    }
}

pub fn configure() {
    config::read("eem_drtio_delay", |r| {
        match r {
            Ok(record) => {
                info!("Loading DRTIO-over-EEM configuration from flash.");
                unsafe {
                    apply_config(&*(record.as_ptr() as *const SerdesConfig));
                    assign_bitslip();
                    csr::eem_transceiver::rx_ready_write(1);
                }
            },

            Err(_) => {
                info!("Calibrate DRTIO-over-EEM...");
                let config;
                unsafe {
                    config = assign_delay();
                    assign_bitslip();
                    csr::eem_transceiver::rx_ready_write(1);
                }

                config::write("eem_drtio_delay", config.as_bytes()).unwrap();
            }
        }
    })
}
