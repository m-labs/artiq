#![no_std]
#![feature(compiler_builtins_lib, alloc, repr_simd, lang_items, const_fn, global_allocator)]

extern crate compiler_builtins;
extern crate alloc;
extern crate cslice;
#[macro_use]
extern crate log;
extern crate byteorder;
extern crate fringe;
extern crate smoltcp;

extern crate alloc_list;
#[macro_use]
extern crate std_artiq as std;
extern crate logger_artiq;
#[macro_use]
extern crate board;
extern crate proto;
extern crate amp;
#[cfg(has_drtio)]
extern crate drtioaux;

use std::boxed::Box;
use smoltcp::wire::{EthernetAddress, IpAddress, IpCidr};
use proto::{mgmt_proto, analyzer_proto, moninj_proto, rpc_proto, session_proto, kernel_proto};
use amp::{mailbox, rpc_queue};

macro_rules! borrow_mut {
    ($x:expr) => ({
        match $x.try_borrow_mut() {
            Ok(x) => x,
            Err(_) => panic!("cannot borrow mutably at {}:{}", file!(), line!())
        }
    })
}

mod config;
mod ethmac;
mod rtio_mgt;

mod urc;
mod sched;
mod cache;
mod rtio_dma;

mod mgmt;
mod kernel;
mod kern_hwreq;
mod session;
#[cfg(any(has_rtio_moninj, has_drtio))]
mod moninj;
#[cfg(has_rtio_analyzer)]
mod analyzer;

fn startup() {
    board::clock::init();
    info!("ARTIQ runtime starting...");
    info!("software version {}", include_str!(concat!(env!("OUT_DIR"), "/git-describe")));
    info!("gateware version {}", board::ident(&mut [0; 64]));

    #[cfg(has_serwb_phy)]
    board::serwb::wait_init();

    let t = board::clock::get_ms();
    info!("press 'e' to erase startup and idle kernels...");
    while board::clock::get_ms() < t + 1000 {
        if unsafe { board::csr::uart::rxtx_read() == b'e' } {
            config::remove("startup_kernel").unwrap();
            config::remove("idle_kernel").unwrap();
            info!("startup and idle kernels erased");
            break
        }
    }
    info!("continuing boot");

    #[cfg(has_i2c)]
    board::i2c::init();
    #[cfg(has_ad9516)]
    board::ad9516::init().expect("cannot initialize AD9516");
    #[cfg(has_hmc830_7043)]
    board::hmc830_7043::init().expect("cannot initialize HMC830/7043");
    #[cfg(has_ad9154)]
    board::ad9154::init().expect("cannot initialize AD9154");

    let hardware_addr;
    match config::read_str("mac", |r| r?.parse()) {
        Err(()) => {
            hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x01]);
            warn!("using default MAC address {}; consider changing it", hardware_addr);
        }
        Ok(addr) => {
            hardware_addr = addr;
            info!("using MAC address {}", hardware_addr);
        }
    }

    let protocol_addr;
    match config::read_str("ip", |r| r?.parse()) {
        Err(()) => {
            protocol_addr = IpAddress::v4(192, 168, 1, 50);
            info!("using default IP address {}", protocol_addr);
        }
        Ok(addr) => {
            protocol_addr = addr;
            info!("using IP address {}", protocol_addr);
        }
    }

    // fn _net_trace_writer<U>(timestamp: u64, printer: smoltcp::wire::PrettyPrinter<U>)
    //         where U: smoltcp::wire::pretty_print::PrettyPrint {
    //     let seconds = timestamp / 1000;
    //     let micros  = timestamp % 1000 * 1000;
    //     print!("\x1b[37m[{:6}.{:06}s]\n{}\x1b[0m", seconds, micros, printer)
    // }

    let net_device = ethmac::EthernetDevice;
    // let net_device = smoltcp::phy::EthernetTracer::new(net_device, _net_trace_writer);
    let arp_cache  = smoltcp::iface::SliceArpCache::new([Default::default(); 8]);
    let mut interface  = smoltcp::iface::EthernetInterface::new(
        Box::new(net_device), Box::new(arp_cache) as Box<smoltcp::iface::ArpCache>,
        hardware_addr, [IpCidr::new(protocol_addr, 0)], None);

    let mut scheduler = sched::Scheduler::new();
    let io = scheduler.io();
    rtio_mgt::startup(&io);
    io.spawn(4096, mgmt::thread);
    io.spawn(16384, session::thread);
    #[cfg(any(has_rtio_moninj, has_drtio))]
    io.spawn(4096, moninj::thread);
    #[cfg(has_rtio_analyzer)]
    io.spawn(4096, analyzer::thread);

    match config::read_str("log_level", |r| r?.parse()) {
        Err(()) => (),
        Ok(log_level_filter) => {
            info!("log level set to {} by `log_level` config key",
                  log_level_filter);
            logger_artiq::BufferLogger::with(|logger|
                logger.set_max_log_level(log_level_filter));
        }
    }

    match config::read_str("uart_log_level", |r| r?.parse()) {
        Err(()) => {
            info!("UART log level set to INFO by default");
        },
        Ok(uart_log_level_filter) => {
            info!("UART log level set to {} by `uart_log_level` config key",
                  uart_log_level_filter);
            logger_artiq::BufferLogger::with(|logger|
                logger.set_uart_log_level(uart_log_level_filter));
        }
    }

    let mut net_stats = ethmac::EthernetStatistics::new();
    loop {
        scheduler.run();

        match interface.poll(&mut *borrow_mut!(scheduler.sockets()),
                             board::clock::get_ms()) {
            Ok(_poll_at) => (),
            Err(smoltcp::Error::Unrecognized) => (),
            Err(err) => warn!("network error: {}", err)
        }

        if let Some(net_stats_diff) = net_stats.update() {
            warn!("ethernet mac:{}", net_stats_diff); // mac:{} (sic)
        }
    }
}

#[global_allocator]
static mut ALLOC: alloc_list::ListAlloc = alloc_list::EMPTY;
static mut LOG_BUFFER: [u8; 1<<17] = [0; 1<<17];

#[no_mangle]
pub extern fn main() -> i32 {
    unsafe {
        extern {
            static mut _fheap: u8;
            static mut _eheap: u8;
        }
        ALLOC.add_range(&mut _fheap, &mut _eheap);

        logger_artiq::BufferLogger::new(&mut LOG_BUFFER[..]).register(startup);

        0
    }
}

#[no_mangle]
pub extern fn exception_handler(vect: u32, _regs: *const u32, pc: u32, ea: u32) {
    panic!("exception {:?} at PC 0x{:x}, EA 0x{:x}", vect, pc, ea)
}

#[no_mangle]
pub extern fn abort() {
    panic!("aborted")
}

#[no_mangle]
#[lang = "panic_fmt"]
pub extern fn panic_fmt(args: core::fmt::Arguments, file: &'static str, line: u32) -> ! {
    println!("panic at {}:{}: {}", file, line, args);

    if config::read_str("panic_reboot", |r| r == Ok("1")) {
        println!("rebooting...");
        unsafe { board::boot::reboot() }
    } else {
        println!("halting.");
        println!("use `artiq_coreconfig write -s panic_reboot 1` to reboot instead");
        loop {}
    }
}

// Allow linking with crates that are built as -Cpanic=unwind even if we use -Cpanic=abort.
// This is never called.
#[allow(non_snake_case)]
#[no_mangle]
pub extern fn _Unwind_Resume() -> ! {
    loop {}
}
