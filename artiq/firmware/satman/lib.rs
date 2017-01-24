#![no_std]
#![feature(libc, const_fn, repr_simd, asm, lang_items)]

extern crate alloc_artiq;
#[macro_use]
extern crate std_artiq as std;
extern crate libc;
#[macro_use]
extern crate log;
extern crate log_buffer;
extern crate board;

use core::fmt::Write;
use logger::BufferLogger;

extern {
    fn putchar(c: libc::c_int) -> libc::c_int;
    fn readchar() -> libc::c_char;
    fn readchar_nonblock() -> libc::c_int;
}

#[macro_export]
macro_rules! print {
    ($($arg:tt)*) => ($crate::print_fmt(format_args!($($arg)*)));
}

#[macro_export]
macro_rules! println {
    ($fmt:expr) => (print!(concat!($fmt, "\n")));
    ($fmt:expr, $($arg:tt)*) => (print!(concat!($fmt, "\n"), $($arg)*));
}

pub struct Console;

impl core::fmt::Write for Console {
    fn write_str(&mut self, s: &str) -> Result<(), core::fmt::Error> {
        for c in s.bytes() { unsafe { putchar(c as i32); } }
        Ok(())
    }
}

pub fn print_fmt(args: self::core::fmt::Arguments) {
    let _ = Console.write_fmt(args);
}

#[no_mangle]
#[lang = "panic_fmt"]
pub extern fn panic_fmt(args: self::core::fmt::Arguments, file: &'static str, line: u32) -> ! {
    let _ = write!(Console, "panic at {}:{}: {}\n", file, line, args);
    let _ = write!(Console, "waiting for debugger...\n");
    unsafe {
        let _ = readchar();
        loop { asm!("l.trap 0") }
    }
}

mod logger;

// Allow linking with crates that are built as -Cpanic=unwind even if we use -Cpanic=abort.
// This is never called.
#[allow(non_snake_case)]
#[no_mangle]
pub extern "C" fn _Unwind_Resume() -> ! {
    loop {}
}

#[no_mangle]
pub unsafe extern fn rust_main() {
    static mut LOG_BUFFER: [u8; 65536] = [0; 65536];
    BufferLogger::new(&mut LOG_BUFFER[..])
                 .register(move || {
        board::clock::init();
        info!("ARTIQ satellite manager starting...");
        info!("software version {}", cfg!(git_describe));
        info!("gateware version {}", board::ident(&mut [0; 64]));

        loop {
        }
    })
}

#[no_mangle]
pub unsafe extern fn isr() {
    use board::{irq, csr};
    extern { fn uart_isr(); }

    let irqs = irq::pending() & irq::get_mask();
    if irqs & (1 << csr::UART_INTERRUPT) != 0 {
        uart_isr()
    }
}
