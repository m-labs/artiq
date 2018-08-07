use board_misoc::csr;

#[derive(PartialEq)]
enum State {
    Down,
    WaitResolution,
    Up
}

static mut GRABBER_STATE: [State; csr::GRABBER_LEN] = [State::Down; csr::GRABBER_LEN];
static mut GRABBER_RESOLUTION: [(u16, u16); csr::GRABBER_LEN] = [(0, 0); csr::GRABBER_LEN];

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

fn get_last_pixels(g: usize) -> (u16, u16) {
    unsafe { ((csr::GRABBER[g].last_x_read)(),
              (csr::GRABBER[g].last_y_read)()) }
}

fn get_video_clock(g: usize) -> u32 {
    let freq_count = unsafe {
        (csr::GRABBER[g].freq_count_read)()
    } as u32;
    2*freq_count*(csr::CONFIG_CLOCK_FREQUENCY/1000)/(511*1000)
}

pub fn tick() {
    for g in 0..csr::GRABBER.len() {
        if unsafe { GRABBER_STATE[g] != State::Down } {
            if !clock_pattern_ok(g) || !pll_locked(g) {
                set_pll_reset(g, true);
                unsafe { GRABBER_STATE[g] = State::Down; }
                info!("grabber{} is down", g);
            }
            if unsafe { GRABBER_STATE[g] == State::WaitResolution } {
                let last_xy = get_last_pixels(g);
                unsafe { GRABBER_RESOLUTION[g] = last_xy; }
                info!("grabber{} frame size: {}x{}",
                    g, last_xy.0 + 1, last_xy.1 + 1);
                info!("grabber{} video clock: {}MHz", g, get_video_clock(g));
                unsafe { GRABBER_STATE[g] = State::Up; }
            } else {
                let last_xy = get_last_pixels(g);
                if unsafe { last_xy != GRABBER_RESOLUTION[g] } {
                    info!("grabber{} frame size: {}x{}",
                        g, last_xy.0 + 1, last_xy.1 + 1);
                    unsafe { GRABBER_RESOLUTION[g] = last_xy; }
                }
            }
        } else {
            if get_pll_reset(g) {
                set_pll_reset(g, false);
            } else {
                if pll_locked(g) {
                    info!("grabber{} PLL is locked", g);
                    if clock_align(g) {
                        info!("grabber{} is up", g);
                        unsafe { GRABBER_STATE[g] = State::WaitResolution; }
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
