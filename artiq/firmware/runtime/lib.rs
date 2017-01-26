#![no_std]
#![feature(libc, repr_simd)]

extern crate alloc_artiq;
#[macro_use]
extern crate std_artiq as std;
extern crate libc;
#[macro_use]
extern crate log;
extern crate logger_artiq;
extern crate byteorder;
extern crate fringe;
extern crate smoltcp;
#[macro_use]
extern crate board;

use std::boxed::Box;
use smoltcp::wire::{EthernetAddress, IpAddress};

extern {
    fn readchar() -> libc::c_char;
    fn readchar_nonblock() -> libc::c_int;
}

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
mod mailbox;
mod rpc_queue;

mod urc;
mod sched;
mod cache;

mod proto;
mod kernel_proto;
mod session_proto;
#[cfg(has_rtio_moninj)]
mod moninj_proto;
#[cfg(has_rtio_analyzer)]
mod analyzer_proto;
mod rpc_proto;

mod kernel;
mod session;
#[cfg(has_rtio_moninj)]
mod moninj;
#[cfg(has_rtio_analyzer)]
mod analyzer;

fn startup() {
    board::clock::init();
    info!("ARTIQ runtime starting...");
    info!("software version {}", cfg!(git_describe));
    info!("gateware version {}", board::ident(&mut [0; 64]));

    let t = board::clock::get_ms();
    info!("press 'e' to erase startup and idle kernels...");
    while board::clock::get_ms() < t + 1000 {
        if unsafe { readchar_nonblock() != 0 && readchar() == b'e' as libc::c_char } {
            config::remove("startup_kernel");
            config::remove("idle_kernel");
            info!("startup and idle kernels erased");
            break
        }
    }
    info!("continuing boot");

    #[cfg(has_i2c)]
    board::i2c::init();
    #[cfg(has_ad9516)]
    board::ad9516::init().expect("cannot initialize ad9516");
    #[cfg(has_converter_spi)]
    board::ad9154::init().expect("cannot initialize ad9154");

    let hardware_addr;
    match EthernetAddress::parse(&config::read_string("mac")) {
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
    match IpAddress::parse(&config::read_string("ip")) {
        Err(()) | Ok(IpAddress::Unspecified) => {
            protocol_addr = IpAddress::v4(192, 168, 1, 50);
            info!("using default IP address {}", protocol_addr);
        }
        Ok(addr) => {
            protocol_addr = addr;
            info!("using IP address {}", protocol_addr);
        }
    }

    fn _net_trace_writer<U>(printer: smoltcp::wire::PrettyPrinter<U>)
            where U: smoltcp::wire::pretty_print::PrettyPrint {
        print!("\x1b[37m{}\x1b[0m", printer)
    }

    let net_device = ethmac::EthernetDevice;
    // let net_device = smoltcp::phy::Tracer::<_, smoltcp::wire::EthernetFrame<&[u8]>>
    //                                      ::new(net_device, _net_trace_writer);
    let arp_cache  = smoltcp::iface::SliceArpCache::new([Default::default(); 8]);
    let mut interface  = smoltcp::iface::EthernetInterface::new(
        Box::new(net_device), Box::new(arp_cache) as Box<smoltcp::iface::ArpCache>,
        hardware_addr, [protocol_addr]);

    let mut scheduler = sched::Scheduler::new();
    let io = scheduler.io();
    rtio_mgt::startup(&io);
    io.spawn(16384, session::thread);
    #[cfg(has_rtio_moninj)]
    io.spawn(4096, moninj::thread);
    #[cfg(has_rtio_analyzer)]
    io.spawn(4096, analyzer::thread);

    loop {
        scheduler.run();

        match interface.poll(&mut *borrow_mut!(scheduler.sockets()),
                             board::clock::get_ms()) {
            Ok(()) => (),
            Err(smoltcp::Error::Exhausted) => (),
            Err(smoltcp::Error::Unrecognized) => (),
            Err(e) => warn!("network error: {}", e)
        }
    }
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
