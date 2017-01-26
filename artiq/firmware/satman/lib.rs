#![no_std]

extern crate alloc_artiq;
#[macro_use]
extern crate std_artiq as std;
#[macro_use]
extern crate log;
extern crate logger_artiq;
extern crate board;

fn startup() {
    board::clock::init();
    info!("ARTIQ satellite manager starting...");
    info!("software version {}", include_str!(concat!(env!("OUT_DIR"), "/git-describe")));
    info!("gateware version {}", board::ident(&mut [0; 64]));

    loop {}
}

use board::{irq, csr};
extern {
    fn uart_init();
    fn uart_isr();

    fn alloc_give(ptr: *mut u8, length: usize);
    static mut _fheap: u8;
    static mut _eheap: u8;
}

#[no_mangle]
pub unsafe extern fn main() -> i32 {
    irq::set_mask(0);
    irq::set_ie(true);
    uart_init();

    alloc_give(&mut _fheap as *mut u8,
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
