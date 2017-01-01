#![no_std]
#![feature(libc, const_fn, repr_simd, asm, lang_items)]

extern crate alloc_artiq;
#[macro_use]
extern crate std_artiq as std;
extern crate libc;
#[macro_use]
extern crate log;
extern crate log_buffer;
extern crate byteorder;
extern crate fringe;
extern crate lwip;
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

mod config;
mod rtio_mgt;
mod mailbox;
mod rpc_queue;

mod urc;
mod sched;
mod logger;
mod cache;

mod proto;
mod kernel_proto;
mod session_proto;
mod moninj_proto;
mod analyzer_proto;
mod rpc_proto;

mod kernel;
mod session;
#[cfg(has_rtio_moninj)]
mod moninj;
#[cfg(has_rtio_analyzer)]
mod analyzer;

extern {
    fn network_init();
    fn lwip_service();
}

include!(concat!(env!("OUT_DIR"), "/git_info.rs"));

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
        info!("booting ARTIQ");
        info!("software version {}", GIT_COMMIT);
        info!("gateware version {}", board::ident(&mut [0; 64]));

        let t = board::clock::get_ms();
        info!("press 'e' to erase startup and idle kernels...");
        while board::clock::get_ms() < t + 1000 {
            if readchar_nonblock() != 0 && readchar() == b'e' as libc::c_char {
                config::remove("startup_kernel");
                config::remove("idle_kernel");
                info!("startup and idle kernels erased");
                break
            }
        }
        info!("continuing boot");

        network_init();

        let mut scheduler = sched::Scheduler::new();
        rtio_mgt::startup(&scheduler);
        scheduler.spawner().spawn(16384, session::thread);
        #[cfg(has_rtio_moninj)]
        scheduler.spawner().spawn(4096, moninj::thread);
        #[cfg(has_rtio_analyzer)]
        scheduler.spawner().spawn(4096, analyzer::thread);

        loop {
            scheduler.run();
            lwip_service();
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

#[no_mangle]
pub fn sys_now() -> u32 {
    board::clock::get_ms() as u32
}

#[no_mangle]
pub fn sys_jiffies() -> u32 {
    board::clock::get_ms() as u32
}
