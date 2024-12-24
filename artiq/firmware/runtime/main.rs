#![feature(lang_items, panic_info_message, const_btree_new, iter_advance_by, never_type)]
#![no_std]

extern crate crc;
extern crate dyld;
extern crate eh;
#[macro_use]
extern crate alloc;
extern crate failure;
#[macro_use]
extern crate failure_derive;
extern crate cslice;
#[macro_use]
extern crate log;
extern crate byteorder;
extern crate fringe;
extern crate managed;
extern crate smoltcp;

extern crate alloc_list;
extern crate unwind_backtrace;
extern crate io;
#[macro_use]
extern crate board_misoc;
extern crate board_artiq;
extern crate logger_artiq;
extern crate proto_artiq;
extern crate riscv;
#[cfg(has_drtio)]
extern crate tar_no_std;

use alloc::collections::BTreeMap;
use core::cell::{RefCell, Cell};
use core::convert::TryFrom;
use smoltcp::wire::HardwareAddress;
use urc::Urc;

use board_misoc::{csr, ident, clock, spiflash, config, net_settings, pmp, boot};
#[cfg(has_ethmac)]
use board_misoc::ethmac;
#[cfg(soc_platform = "kasli")]
use board_misoc::irq;
use board_misoc::net_settings::{Ipv4AddrConfig};
#[cfg(has_drtio)]
use board_artiq::drtioaux;
use board_artiq::drtio_routing;
use board_artiq::{mailbox, rpc_queue};
use proto_artiq::{mgmt_proto, moninj_proto, rpc_proto, session_proto, kernel_proto};
#[cfg(has_wrpll)]
use board_artiq::si549;
#[cfg(has_drtio_eem)]
use board_artiq::drtio_eem;
#[cfg(has_rtio_analyzer)]
use proto_artiq::analyzer_proto;

use riscv::register::{mcause, mepc, mtval};
use smoltcp::iface::Routes;
use ip_addr_storage::InterfaceBuilderEx;

mod rtio_clocking;
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
mod dhcp;
mod ip_addr_storage;

#[cfg(has_grabber)]
fn grabber_thread(io: sched::Io) {
    loop {
        board_artiq::grabber::tick();
        io.sleep(200).unwrap();
    }
}

fn setup_log_levels() {
    match config::read_str("log_level", |r| r.map(|s| s.parse())) {
        Ok(Ok(log_level_filter)) => {
            info!("log level set to {} by `log_level` config key",
                  log_level_filter);
            log::set_max_level(log_level_filter);
        }
        _ => info!("log level set to INFO by default")
    }
    match config::read_str("uart_log_level", |r| r.map(|s| s.parse())) {
        Ok(Ok(uart_log_level_filter)) => {
            info!("UART log level set to {} by `uart_log_level` config key",
                  uart_log_level_filter);
            logger_artiq::BufferLogger::with(|logger|
                logger.set_uart_log_level(uart_log_level_filter));
        }
        _ => info!("UART log level set to INFO by default")
    }
}

fn startup() {
    clock::init();
    info!("ARTIQ runtime starting...");
    info!("software ident {}", csr::CONFIG_IDENTIFIER_STR);
    info!("gateware ident {}", ident::read(&mut [0; 64]));

    setup_log_levels();
    #[cfg(has_i2c)]
    board_misoc::i2c::init().expect("I2C initialization failed");
    #[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
    let (mut io_expander0, mut io_expander1);
    #[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
    {
        io_expander0 = board_misoc::io_expander::IoExpander::new(0).unwrap();
        io_expander1 = board_misoc::io_expander::IoExpander::new(1).unwrap();
        io_expander0.init().expect("I2C I/O expander #0 initialization failed");
        io_expander1.init().expect("I2C I/O expander #1 initialization failed");

        // Actively drive TX_DISABLE to false on SFP0..3
        io_expander0.set_oe(0, 1 << 1).unwrap();
        io_expander0.set_oe(1, 1 << 1).unwrap();
        io_expander1.set_oe(0, 1 << 1).unwrap();
        io_expander1.set_oe(1, 1 << 1).unwrap();
        io_expander0.set(0, 1, false);
        io_expander0.set(1, 1, false);
        io_expander1.set(0, 1, false);
        io_expander1.set(1, 1, false);
        io_expander0.service().unwrap();
        io_expander1.service().unwrap();
    }
    rtio_clocking::init();

    #[cfg(has_drtio_eem)]
    drtio_eem::init();

    let mut net_device = unsafe { ethmac::EthernetDevice::new() };
    net_device.reset_phy_if_any();

    let net_device = {
        use smoltcp::phy::Tracer;

        // We can't create the function pointer as a separate variable here because the type of
        // the packet argument Packet isn't accessible and rust's type inference isn't sufficient
        // to propagate in to a local var.
        match config::read_str("net_trace", |r| r.map(|s| s == "1")) {
            Ok(true) => Tracer::new(net_device, |timestamp, packet| {
                print!("\x1b[37m[{:6}.{:03}s]\n{}\x1b[0m\n",
                       timestamp.secs(), timestamp.millis(), packet)
            }),
            _ => Tracer::new(net_device, |_, _| {}),
        }
    };

    let neighbor_cache =
        smoltcp::iface::NeighborCache::new(alloc::collections::btree_map::BTreeMap::new());
    let net_addresses = net_settings::get_adresses();
    info!("network addresses: {}", net_addresses);
    let use_dhcp = if matches!(net_addresses.ipv4_addr, Ipv4AddrConfig::UseDhcp) {
        info!("Will try to acquire an IPv4 address with DHCP");
        true
    } else {
        false
    };
    let mut interface = smoltcp::iface::InterfaceBuilder::new(net_device, vec![])
        .hardware_addr(HardwareAddress::Ethernet(net_addresses.hardware_addr))
        .init_ip_addrs(&net_addresses)
        .neighbor_cache(neighbor_cache)
        .routes(Routes::new(BTreeMap::new()))
        .finalize();

    if !use_dhcp {
        if let Some(ipv4_default_route) = net_addresses.ipv4_default_route {
            interface.routes_mut().add_default_ipv4_route(ipv4_default_route).unwrap();
        }
    }

    if let Some(ipv6_default_route) = net_addresses.ipv6_default_route {
        interface.routes_mut().add_default_ipv6_route(ipv6_default_route).unwrap();
    }

    #[cfg(has_drtio)]
    let drtio_routing_table = urc::Urc::new(RefCell::new(
        drtio_routing::config_routing_table(csr::DRTIO.len())));
    #[cfg(not(has_drtio))]
    let drtio_routing_table = urc::Urc::new(RefCell::new(
        drtio_routing::RoutingTable::default_empty()));
    let up_destinations = urc::Urc::new(RefCell::new(
        [false; drtio_routing::DEST_COUNT]));
    #[cfg(has_drtio_routing)]
    drtio_routing::interconnect_disable_all();
    let aux_mutex = sched::Mutex::new();

    let ddma_mutex = sched::Mutex::new();
    let subkernel_mutex = sched::Mutex::new();
    let restart_idle = Urc::new(Cell::new(false));

    let mut scheduler = sched::Scheduler::new(interface);
    let io = scheduler.io();

    if use_dhcp {
        io.spawn(4096, dhcp::dhcp_thread);
    }

    rtio_mgt::startup(&io, &aux_mutex, &drtio_routing_table, &up_destinations, &ddma_mutex, &subkernel_mutex);
    {
        let restart_idle = restart_idle.clone();
        let aux_mutex = aux_mutex.clone();
        let ddma_mutex = ddma_mutex.clone();
        let subkernel_mutex = subkernel_mutex.clone();
        let drtio_routing_table = drtio_routing_table.clone();
        io.spawn(4096, move |io| { mgmt::thread(io, &restart_idle, &aux_mutex, &ddma_mutex, &subkernel_mutex, &drtio_routing_table) });
    }
    {
        let aux_mutex = aux_mutex.clone();
        let drtio_routing_table = drtio_routing_table.clone();
        let up_destinations = up_destinations.clone();
        let ddma_mutex = ddma_mutex.clone();
        let subkernel_mutex = subkernel_mutex.clone();
        let restart_idle = restart_idle.clone();
        io.spawn(32768, move |io| { session::thread(io, &aux_mutex, &drtio_routing_table, &up_destinations, &ddma_mutex, &subkernel_mutex, &restart_idle) });
    }
    #[cfg(any(has_rtio_moninj, has_drtio))]
    {
        let aux_mutex = aux_mutex.clone();
        let ddma_mutex = ddma_mutex.clone();
        let subkernel_mutex = subkernel_mutex.clone();
        let drtio_routing_table = drtio_routing_table.clone();
        io.spawn(4096, move |io| { moninj::thread(io, &aux_mutex, &ddma_mutex, &subkernel_mutex, &drtio_routing_table) });
    }
    #[cfg(has_rtio_analyzer)]
    {
        let aux_mutex = aux_mutex.clone();
        let ddma_mutex = ddma_mutex.clone();
        let subkernel_mutex = subkernel_mutex.clone();
        let drtio_routing_table = drtio_routing_table.clone();
        let up_destinations = up_destinations.clone();
        io.spawn(16384, move |io| { analyzer::thread(io, &aux_mutex, &ddma_mutex, &subkernel_mutex, &drtio_routing_table, &up_destinations) });
    }

    #[cfg(has_grabber)]
    io.spawn(4096, grabber_thread);

    let mut net_stats = ethmac::EthernetStatistics::new();
    loop {
        scheduler.run();
        scheduler.run_network();

        if let Some(_net_stats_diff) = net_stats.update() {
            debug!("ethernet mac:{}", ethmac::EthernetStatistics::new());
        }

        #[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
        {
            io_expander0.service().expect("I2C I/O expander #0 service failed");
            io_expander1.service().expect("I2C I/O expander #1 service failed");
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
            static mut _sstack_guard: u8;
        }
        ALLOC.add_range(&mut _fheap, &mut _eheap);

        pmp::init_stack_guard(&_sstack_guard as *const u8 as usize);

        #[cfg(soc_platform = "kasli")]
        irq::enable_interrupts();
        #[cfg(has_wrpll)]
        irq::enable(csr::WRPLL_INTERRUPT);

        logger_artiq::BufferLogger::new(&mut LOG_BUFFER[..]).register(||
            boot::start_user(startup as usize)
        );

        0
    }
}

#[derive(Debug, Clone, Copy)]
#[repr(C)]
pub struct TrapFrame {
    pub ra: usize,
    pub t0: usize,
    pub t1: usize,
    pub t2: usize,
    pub t3: usize,
    pub t4: usize,
    pub t5: usize,
    pub t6: usize,
    pub a0: usize,
    pub a1: usize,
    pub a2: usize,
    pub a3: usize,
    pub a4: usize,
    pub a5: usize,
    pub a6: usize,
    pub a7: usize,
}

#[no_mangle]
pub extern fn exception(regs: *const TrapFrame) {
    let pc = mepc::read();
    let cause = mcause::read().cause();
    match cause {
        mcause::Trap::Interrupt(_source) => {
            #[cfg(has_wrpll)]
            if irq::is_pending(csr::WRPLL_INTERRUPT) {
                si549::wrpll::interrupt_handler();
            }
        },

        mcause::Trap::Exception(mcause::Exception::UserEnvCall) => {
            unsafe {
                if (*regs).a7 == 0 {
                    pmp::pop_pmp_region()
                } else {
                    pmp::push_pmp_region((*regs).a7)
                }
            }
            mepc::write(pc + 4);
        },

        mcause::Trap::Exception(e) => {
            println!("Trap frame: {:x?}", unsafe { *regs });

            fn hexdump(addr: u32) {
                let addr = (addr - addr % 4) as *const u32;
                let mut ptr  = addr;
                println!("@ {:08p}", ptr);
                for _ in 0..4 {
                    print!("+{:04x}: ", ptr as usize - addr as usize);
                    print!("{:08x} ",   unsafe { *ptr }); ptr = ptr.wrapping_offset(1);
                    print!("{:08x} ",   unsafe { *ptr }); ptr = ptr.wrapping_offset(1);
                    print!("{:08x} ",   unsafe { *ptr }); ptr = ptr.wrapping_offset(1);
                    print!("{:08x}\n",  unsafe { *ptr }); ptr = ptr.wrapping_offset(1);
                }
            }

            hexdump(u32::try_from(pc).unwrap());
            let mtval = mtval::read();
            panic!("exception {:?} at PC 0x{:x}, trap value 0x{:x}", e, u32::try_from(pc).unwrap(), mtval)
        }
    }
}

#[no_mangle]
pub extern fn abort() {
    println!("aborted");
    loop {}
}

#[no_mangle] // https://github.com/rust-lang/rust/issues/{38281,51647}
#[lang = "oom"] // https://github.com/rust-lang/rust/issues/51540
pub fn oom(layout: core::alloc::Layout) -> ! {
    panic!("heap view: {}\ncannot allocate layout: {:?}", unsafe { &ALLOC }, layout)
}

#[no_mangle] // https://github.com/rust-lang/rust/issues/{38281,51647}
#[panic_handler]
pub fn panic_impl(info: &core::panic::PanicInfo) -> ! {
    #[cfg(has_error_led)]
    unsafe {
        csr::error_led::out_write(1);
    }

    if let Some(location) = info.location() {
        print!("panic at {}:{}:{}", location.file(), location.line(), location.column());
    } else {
        print!("panic at unknown location");
    }
    if let Some(message) = info.message() {
        println!(": {}", message);
    } else {
        println!("");
    }

    println!("backtrace for software version {}:", csr::CONFIG_IDENTIFIER_STR);
    let _ = unwind_backtrace::backtrace(|ip| {
        // Backtrace gives us the return address, i.e. the address after jal(r) insn,
        // but we're interested in the call instruction.
        println!("{:#08x}", ip - 4);
    });

    if config::read_str("panic_reset", |r| r == Ok("1")) && 
        cfg!(any(soc_platform = "kasli", soc_platform = "kc705")) {
        println!("restarting...");
        unsafe {
            kernel::stop();
            spiflash::reload();
        }
    } else {
        println!("halting.");
        println!("use `artiq_coremgmt config write -s panic_reset 1` to restart instead");
        loop {}
    }
}
