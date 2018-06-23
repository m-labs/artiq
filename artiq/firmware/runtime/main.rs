#![feature(lang_items, alloc, global_allocator, try_from, nonzero, nll, needs_panic_runtime, asm)]
#![no_std]
#![needs_panic_runtime]

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

use core::convert::TryFrom;
use smoltcp::wire::{EthernetAddress, IpAddress, IpCidr};

use board_misoc::{csr, irq, ident, clock, boot, config};
#[cfg(has_ethmac)]
use board_misoc::ethmac;
#[cfg(has_drtio)]
use board_artiq::drtioaux;
use board_artiq::{mailbox, rpc_queue};
use proto_artiq::{mgmt_proto, moninj_proto, rpc_proto, session_proto,kernel_proto};
#[cfg(has_rtio_analyzer)]
use proto_artiq::analyzer_proto;

#[cfg(has_rtio_core)]
mod rtio_mgt;

mod urc;
mod sched;
mod cache;
mod rtio_dma;

mod mgmt;
mod profiler;
mod kernel;
mod kern_hwreq;
mod watchdog;
mod session;
#[cfg(any(has_rtio_moninj, has_drtio))]
mod moninj;
#[cfg(has_rtio_analyzer)]
mod analyzer;

#[cfg(has_ad9154)]
const SYSREF_PHASE_FPGA: u16 = 20;
#[cfg(has_ad9154)]
const SYSREF_PHASE_DAC: u16 = 31;

fn startup() {
    irq::set_mask(0);
    irq::set_ie(true);
    clock::init();
    info!("ARTIQ runtime starting...");
    info!("software version {}", include_str!(concat!(env!("OUT_DIR"), "/git-describe")));
    info!("gateware version {}", ident::read(&mut [0; 64]));

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

    #[cfg(has_slave_fpga_cfg)]
    board_artiq::slave_fpga::load().expect("cannot load RTM FPGA gateware");
    #[cfg(has_serwb_phy_amc)]
    board_artiq::serwb::wait_init();

    #[cfg(has_uart)] {
        let t = clock::get_ms();
        info!("press 'e' to erase startup and idle kernels...");
        while clock::get_ms() < t + 1000 {
            if unsafe { csr::uart::rxtx_read() == b'e' } {
                config::remove("startup_kernel").unwrap();
                config::remove("idle_kernel").unwrap();
                info!("startup and idle kernels erased");
                break
            }
        }
        info!("continuing boot");
    }

    #[cfg(has_i2c)]
    board_artiq::i2c::init();
    #[cfg(si5324_as_synthesizer)]
    setup_si5324_as_synthesizer();
    #[cfg(has_hmc830_7043)]
    /* must be the first SPI init because of HMC830 SPI mode selection */
    board_artiq::hmc830_7043::init().expect("cannot initialize HMC830/7043");
    #[cfg(has_ad9154)]
    board_artiq::ad9154::init(SYSREF_PHASE_FPGA, SYSREF_PHASE_DAC);
    #[cfg(has_allaki_atts)]
    board_artiq::hmc542::program_all(8/*=4dB*/);

    #[cfg(has_ethmac)]
    startup_ethernet();
    #[cfg(not(has_ethmac))]
    {
        info!("done");
        loop {}
    }
}

#[cfg(si5324_as_synthesizer)]
fn setup_si5324_as_synthesizer()
{
    // 125MHz output, from 100MHz CLKIN2 reference, 586 Hz
    #[cfg(all(not(si5324_sayma_ref), rtio_frequency = "125.0", si5324_ext_ref))]
    const SI5324_SETTINGS: board_artiq::si5324::FrequencySettings
        = board_artiq::si5324::FrequencySettings {
        n1_hs  : 10,
        nc1_ls : 4,
        n2_hs  : 10,
        n2_ls  : 260,
        n31    : 65,
        n32    : 52,
        bwsel  : 4,
        crystal_ref: false
    };
    // 125MHz output, from crystal, 7 Hz
    #[cfg(all(not(si5324_sayma_ref), rtio_frequency = "125.0", not(si5324_ext_ref)))]
    const SI5324_SETTINGS: board_artiq::si5324::FrequencySettings
        = board_artiq::si5324::FrequencySettings {
        n1_hs  : 10,
        nc1_ls : 4,
        n2_hs  : 10,
        n2_ls  : 19972,
        n31    : 4993,
        n32    : 4565,
        bwsel  : 4,
        crystal_ref: true
    };
    // 150MHz output, from crystal
    #[cfg(all(not(si5324_sayma_ref), rtio_frequency = "150.0", not(si5324_ext_ref)))]
    const SI5324_SETTINGS: board_artiq::si5324::FrequencySettings
        = board_artiq::si5324::FrequencySettings {
        n1_hs  : 9,
        nc1_ls : 4,
        n2_hs  : 10,
        n2_ls  : 33732,
        n31    : 9370,
        n32    : 7139,
        bwsel  : 3,
        crystal_ref: true
    };
    // 100MHz output, from crystal (reference for HMC830)
    #[cfg(si5324_sayma_ref)]
    const SI5324_SETTINGS: board_artiq::si5324::FrequencySettings
        = board_artiq::si5324::FrequencySettings {
        n1_hs  : 9,
        nc1_ls : 6,
        n2_hs  : 10,
        n2_ls  : 33732,
        n31    : 9370,
        n32    : 7139,
        bwsel  : 3,
        crystal_ref: true
    };
    board_artiq::si5324::setup(&SI5324_SETTINGS,
        board_artiq::si5324::Input::Ckin2).expect("cannot initialize Si5324");
}

#[cfg(has_grabber)]
fn grabber_thread(io: sched::Io) {
    loop {
        board_artiq::grabber::tick();
        io.sleep(200).unwrap();
    }
}

#[cfg(has_ethmac)]
fn startup_ethernet() {
    let hardware_addr;
    match config::read_str("mac", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => {
            hardware_addr = addr;
            info!("using MAC address {}", hardware_addr);
        }
        _ => {
            hardware_addr = EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x01]);
            warn!("using default MAC address {}; consider changing it", hardware_addr);
        }
    }

    let protocol_addr;
    match config::read_str("ip", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => {
            protocol_addr = addr;
            info!("using IP address {}", protocol_addr);
        }
        _ => {
            protocol_addr = IpAddress::v4(192, 168, 1, 50);
            info!("using default IP address {}", protocol_addr);
        }
    }

    let mut net_device = unsafe { ethmac::EthernetDevice::new() };
    net_device.reset_phy_if_any();

    let net_device = {
        use smoltcp::wire::PrettyPrinter;
        use smoltcp::wire::EthernetFrame;

        fn net_trace_writer(timestamp: u64, printer: PrettyPrinter<EthernetFrame<&[u8]>>) {
            let seconds = timestamp / 1000;
            let micros  = timestamp % 1000 * 1000;
            print!("\x1b[37m[{:6}.{:06}s]\n{}\x1b[0m\n", seconds, micros, printer)
        }

        fn net_trace_silent(_timestamp: u64, _printer: PrettyPrinter<EthernetFrame<&[u8]>>) {}

        let net_trace_fn: fn(u64, PrettyPrinter<EthernetFrame<&[u8]>>);
        match config::read_str("net_trace", |r| r.map(|s| s == "1")) {
            Ok(true) => net_trace_fn = net_trace_writer,
            _ => net_trace_fn = net_trace_silent
        }
        smoltcp::phy::EthernetTracer::new(net_device, net_trace_fn)
    };

    let mut neighbor_map = [None; 8];
    let neighbor_cache =
        smoltcp::iface::NeighborCache::new(&mut neighbor_map[..]);
    let mut interface  =
        smoltcp::iface::EthernetInterfaceBuilder::new(net_device)
                       .neighbor_cache(neighbor_cache)
                       .ethernet_addr(hardware_addr)
                       .ip_addrs([IpCidr::new(protocol_addr, 0)])
                       .finalize();

    let mut scheduler = sched::Scheduler::new();
    let io = scheduler.io();
    #[cfg(has_rtio_core)]
    rtio_mgt::startup(&io);
    io.spawn(4096, mgmt::thread);
    io.spawn(16384, session::thread);
    #[cfg(any(has_rtio_moninj, has_drtio))]
    io.spawn(4096, moninj::thread);
    #[cfg(has_rtio_analyzer)]
    io.spawn(4096, analyzer::thread);
    #[cfg(has_grabber)]
    io.spawn(4096, grabber_thread);

    let mut net_stats = ethmac::EthernetStatistics::new();
    loop {
        scheduler.run();

        {
            let sockets = &mut *scheduler.sockets().borrow_mut();
            loop {
                match interface.poll(sockets, clock::get_ms()) {
                    Ok(true) => (),
                    Ok(false) => break,
                    Err(smoltcp::Error::Unrecognized) => (),
                    Err(err) => debug!("network error: {}", err)
                }
            }
        }

        if let Some(_net_stats_diff) = net_stats.update() {
            debug!("ethernet mac:{}", ethmac::EthernetStatistics::new());
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
pub extern fn exception(vect: u32, _regs: *const u32, pc: u32, ea: u32) {
    let vect = irq::Exception::try_from(vect).expect("unknown exception");
    match vect {
        irq::Exception::Interrupt =>
            while irq::pending_mask() != 0 {
                match () {
                    #[cfg(has_timer1)]
                    () if irq::is_pending(csr::TIMER1_INTERRUPT) =>
                        profiler::sample(pc as usize),
                    _ => panic!("spurious irq {}", irq::pending_mask().trailing_zeros())
                }
            },
        _ => {
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

            hexdump(pc);
            hexdump(ea);
            panic!("exception {:?} at PC 0x{:x}, EA 0x{:x}", vect, pc, ea)
        }
    }
}

#[no_mangle]
pub extern fn abort() {
    println!("aborted");
    loop {}
}

#[no_mangle]
#[lang = "panic_fmt"]
pub extern fn panic_fmt(args: core::fmt::Arguments, file: &'static str,
                        line: u32, column: u32) -> ! {
    irq::set_ie(false);

    println!("panic at {}:{}:{}: {}", file, line, column, args);

    println!("backtrace for software version {}:",
             include_str!(concat!(env!("OUT_DIR"), "/git-describe")));
    let _ = unwind_backtrace::backtrace(|ip| {
        // Backtrace gives us the return address, i.e. the address after the delay slot,
        // but we're interested in the call instruction.
        println!("{:#08x}", ip - 2 * 4);
    });

    if config::read_str("panic_reset", |r| r == Ok("1")) {
        println!("restarting...");
        unsafe { boot::reset() }
    } else {
        println!("halting.");
        println!("use `artiq_coreconfig write -s panic_reset 1` to restart instead");
        loop {}
    }
}
