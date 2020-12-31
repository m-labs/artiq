use board_misoc::csr;

#[derive(PartialEq, Clone, Copy)]
enum State {
    Reset,
    ExitReset,
    Lock,
    Align,
    Watch
}

#[derive(Clone, Copy)]
struct Info {
    state: State,
    frame_size: (u16, u16),
}

static mut INFO: [Info; csr::GRABBER_LEN] =
    [Info { state: State::Reset, frame_size: (0, 0) }; csr::GRABBER_LEN];

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
        let next = match unsafe { INFO[g].state } {
            State::Reset => {
                set_pll_reset(g, true);
                unsafe { INFO[g].frame_size = (0, 0); }
                State::ExitReset
            }
            State::ExitReset => {
                if get_pll_reset(g) {
                    set_pll_reset(g, false);
                    State::Lock
                } else {
                    State::ExitReset
                }
            }
            State::Lock => {
                if pll_locked(g) {
                    info!("grabber{} locked: {}MHz", g, get_video_clock(g));
                    State::Align
                } else {
                    State::Lock
                }
            }
            State::Align => {
                if pll_locked(g) {
                    if clock_align(g) {
                        info!("grabber{} alignment success", g);
                        State::Watch
                    } else {
                        info!("grabber{} alignment failure", g);
                        State::Reset
                    }
                } else {
                    info!("grabber{} lock lost", g);
                    State::Reset
                }
            }
            State::Watch => {
                if pll_locked(g) {
                    if clock_pattern_ok(g) {
                        let last_xy = get_last_pixels(g);
                        if last_xy != unsafe { INFO[g].frame_size } {
                            // x capture is on ~LVAL which is after
                            // the last increment on DVAL
                            // y capture is on ~FVAL which coincides with the
                            // last increment on ~LVAL
                            info!("grabber{} frame size: {}x{}",
                                g, last_xy.0, last_xy.1 + 1);
                            unsafe { INFO[g].frame_size = last_xy }
                        }
                        State::Watch
                    } else {
                        info!("grabber{} alignment lost", g);
                        State::Reset
                    }
                } else {
                    info!("grabber{} lock lost", g);
                    State::Reset
                }
            }
        };
        unsafe { INFO[g].state = next; }
    }
}
