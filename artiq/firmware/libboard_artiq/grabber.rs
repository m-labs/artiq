use board_misoc::csr;

static mut GRABBER_UP: &'static mut [bool] = &mut [false; csr::GRABBER_LEN];

fn get_pll_reset(g: usize) -> bool {
    unsafe { (csr::GRABBER[g].pll_reset_read)() != 0 }
}

fn set_pll_reset(g: usize, reset: bool) {
    let val = if reset { 1 } else { 0 };
    unsafe { (csr::GRABBER[g].pll_reset_write)(val) }   
}

fn pll_locked(g: usize) -> bool {
    unsafe { (csr::GRABBER[g].pll_locked_read)() != 0 }
}

fn clock_pattern_ok(g: usize) -> bool {
    unsafe { (csr::GRABBER[g].clk_sampled_read)() == 0b1100011 }
}

fn clock_pattern_ok_filter(g: usize) -> bool {
    for _ in 0..128 {
        if !clock_pattern_ok(g) {
            return false;
        }
    }
    true
}

fn phase_shift(g: usize, direction: u8) {
    unsafe {
        (csr::GRABBER[g].phase_shift_write)(direction);
        while (csr::GRABBER[g].phase_shift_done_read)() == 0 {}
    }
}

fn clock_align(g: usize) -> bool {
    while clock_pattern_ok_filter(g) {
        phase_shift(g, 1);
    }
    phase_shift(g, 1);

    let mut count = 0;
    while !clock_pattern_ok_filter(g) {
        phase_shift(g, 1);
        count += 1;
        if count > 1024 {
            return false;
        }
    }

    let mut window = 1;
    phase_shift(g, 1);
    while clock_pattern_ok_filter(g) {
        phase_shift(g, 1);
        window += 1;
    }

    for _ in 0..window/2 {
        phase_shift(g, 0);
    }

    true
}

pub fn tick() {
    for g in 0..csr::GRABBER.len() {
        if unsafe { GRABBER_UP[g] } {
            if !clock_pattern_ok(g) || !pll_locked(g) {
                set_pll_reset(g, true);
                unsafe { GRABBER_UP[g] = false; }
                info!("grabber{} is down", g);
            }
        } else {
            if get_pll_reset(g) {
                set_pll_reset(g, false);
            } else {
                if pll_locked(g) {
                    info!("grabber{} PLL is locked", g);
                    if clock_align(g) {
                        info!("grabber{} is up", g);
                        unsafe { GRABBER_UP[g] = true; }
                    } else {
                        set_pll_reset(g, true);
                    }
                } else {
                    set_pll_reset(g, true);
                }
            }
        }
    }
}
