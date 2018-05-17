use board_misoc::{csr, clock};

const PIN_LE:    u32 = 1 << 0;
const PIN_SIN:   u32 = 1 << 1;
const PIN_CLK:   u32 = 1 << 2;
const PIN_RST_N: u32 = 1 << 3;
const PIN_RST:   u32 = PIN_RST_N;

const CARDS:    usize = 4;
const CHANNELS: usize = 2;

fn set_pins(card_index: usize, chan_index: usize, pins: u32) {
    let pins = pins ^ PIN_RST_N;
    let shift = (card_index * 2 + chan_index)*4;
    unsafe {
        let state = csr::allaki_atts::out_read();
        let state = state & !(0xf << shift);
        let state = state | (pins << shift);
        csr::allaki_atts::out_write(state);
    }
    clock::spin_us(100);
}

/// Attenuation is in units of 0.5 dB, from 0 dB (0) to 31.5 dB (63).
pub fn program(card_index: usize, chan_index: usize, atten: u8) {
    assert!(card_index < 4 && chan_index < 2);

    info!("card {} channel {} set to {}{} dB",
          card_index, chan_index,
          atten / 2, if atten % 2 != 0 { ".5" } else { "" });

    // 0b111111 = 0dB
    // 0b111110 = 0.5dB
    // 0b111101 = 1dB
    // 0b111100 = 1.5dB
    // ...
    // 0b011111 = 16dB
    // ...
    // 0b000000 = 31.5dB
    let atten = !atten << 2;

    let set_pins = |pins| set_pins(card_index, chan_index, pins);
    set_pins(PIN_RST);
    set_pins(0);
    for n in (0..8).rev() {
        let sin = if atten & 1 << n != 0 { PIN_SIN } else { 0 };
        set_pins(sin);
        set_pins(sin | PIN_CLK);
    }
    set_pins(PIN_LE);
}

/// See `program`.
pub fn program_all(atten: u8) {
    for card in 0..CARDS {
        for chan in 0..CHANNELS {
            program(card, chan, atten)
        }
    }
}
