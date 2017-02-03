#![feature(compiler_builtins_lib)]
#![no_std]

extern crate compiler_builtins;
extern crate alloc_artiq;
#[macro_use]
extern crate std_artiq as std;
#[macro_use]
extern crate log;
extern crate logger_artiq;
extern crate board;

#[cfg(rtio_frequency = "62.5")]
const SI5324_SETTINGS: board::si5324::FrequencySettings
        = board::si5324::FrequencySettings {
    n1_hs  : 10,
    nc1_ls : 8,
    n2_hs  : 10,
    n2_ls  : 20112,
    n31    : 2514,
    n32    : 4597
};

#[cfg(rtio_frequency = "150.0")]
const SI5324_SETTINGS: board::si5324::FrequencySettings
        = board::si5324::FrequencySettings {
    n1_hs  : 9,
    nc1_ls : 4,
    n2_hs  : 10,
    n2_ls  : 33732,
    n31    : 9370,
    n32    : 7139
};

fn startup() {
    board::clock::init();
    info!("ARTIQ satellite manager starting...");
    info!("software version {}", include_str!(concat!(env!("OUT_DIR"), "/git-describe")));
    info!("gateware version {}", board::ident(&mut [0; 64]));

    #[cfg(has_ad9516)]
    board::ad9516::init().expect("cannot initialize ad9516");
    board::i2c::init();
    board::si5324::setup_hitless_clock_switching(&SI5324_SETTINGS).expect("cannot initialize si5324");

    loop {}
}

use board::{irq, csr};
extern {
    fn uart_init();
    fn uart_isr();

    static mut _fheap: u8;
    static mut _eheap: u8;
}

#[no_mangle]
pub unsafe extern fn main() -> i32 {
    irq::set_mask(0);
    irq::set_ie(true);
    uart_init();

    alloc_artiq::seed(&mut _fheap as *mut u8,
                      &_eheap as *const u8 as usize - &_fheap as *const u8 as usize);

    static mut LOG_BUFFER: [u8; 65536] = [0; 65536];
    logger_artiq::BufferLogger::new(&mut LOG_BUFFER[..]).register(startup);
    0
}

#[no_mangle]
pub unsafe extern fn isr() {
    let irqs = irq::pending() & irq::get_mask();
    if irqs & (1 << csr::UART_INTERRUPT) != 0 {
        uart_isr()
    }
}

// Allow linking with crates that are built as -Cpanic=unwind even if we use -Cpanic=abort.
// This is never called.
#[allow(non_snake_case)]
#[no_mangle]
pub extern "C" fn _Unwind_Resume() -> ! {
    loop {}
}
