#![feature(lang_items, global_allocator)]
#![no_std]

extern crate alloc_list;
extern crate std_artiq as std;
#[macro_use]
extern crate log;
extern crate logger_artiq;
#[macro_use]
extern crate board;
extern crate board_artiq;
extern crate drtioaux;

use board::csr;
use board_artiq::{i2c, spi, si5324};
#[cfg(has_serwb_phy_amc)]
use board_artiq::serwb;
#[cfg(has_hmc830_7043)]
use board_artiq::hmc830_7043;

fn process_aux_packet(p: &drtioaux::Packet) {
    // In the code below, *_chan_sel_write takes an u8 if there are fewer than 256 channels,
    // and u16 otherwise; hence the `as _` conversion.
    match *p {
        drtioaux::Packet::EchoRequest => drtioaux::hw::send_link(0, &drtioaux::Packet::EchoReply).unwrap(),

        drtioaux::Packet::RtioErrorRequest => {
            let errors;
            unsafe {
                errors = (csr::DRTIO[0].rtio_error_read)();
            }
            if errors & 1 != 0 {
                let channel;
                unsafe {
                    channel = (csr::DRTIO[0].sequence_error_channel_read)();
                    (csr::DRTIO[0].rtio_error_write)(1);
                }
                drtioaux::hw::send_link(0, &drtioaux::Packet::RtioErrorSequenceErrorReply { channel: channel }).unwrap();
            } else if errors & 2 != 0 {
                let channel;
                unsafe {
                    channel = (csr::DRTIO[0].collision_channel_read)();
                    (csr::DRTIO[0].rtio_error_write)(2);
                }
                drtioaux::hw::send_link(0, &drtioaux::Packet::RtioErrorCollisionReply { channel: channel }).unwrap();
            } else if errors & 4 != 0 {
                let channel;
                unsafe {
                    channel = (board::csr::DRTIO[0].busy_channel_read)();
                    (board::csr::DRTIO[0].rtio_error_write)(4);
                }
                drtioaux::hw::send_link(0, &drtioaux::Packet::RtioErrorBusyReply { channel: channel }).unwrap();
            }
            else {
                drtioaux::hw::send_link(0, &drtioaux::Packet::RtioNoErrorReply).unwrap();
            }
        }

        drtioaux::Packet::MonitorRequest { channel, probe } => {
            let value;
            #[cfg(has_rtio_moninj)]
            unsafe {
                csr::rtio_moninj::mon_chan_sel_write(channel as _);
                csr::rtio_moninj::mon_probe_sel_write(probe);
                csr::rtio_moninj::mon_value_update_write(1);
                value = csr::rtio_moninj::mon_value_read();
            }
            #[cfg(not(has_rtio_moninj))]
            {
                value = 0;
            }
            let reply = drtioaux::Packet::MonitorReply { value: value as u32 };
            drtioaux::hw::send_link(0, &reply).unwrap();
        },
        drtioaux::Packet::InjectionRequest { channel, overrd, value } => {
            #[cfg(has_rtio_moninj)]
            unsafe {
                csr::rtio_moninj::inj_chan_sel_write(channel as _);
                csr::rtio_moninj::inj_override_sel_write(overrd);
                csr::rtio_moninj::inj_value_write(value);
            }
        },
        drtioaux::Packet::InjectionStatusRequest { channel, overrd } => {
            let value;
            #[cfg(has_rtio_moninj)]
            unsafe {
                csr::rtio_moninj::inj_chan_sel_write(channel as _);
                csr::rtio_moninj::inj_override_sel_write(overrd);
                value = csr::rtio_moninj::inj_value_read();
            }
            #[cfg(not(has_rtio_moninj))]
            {
                value = 0;
            }
            let reply = drtioaux::Packet::InjectionStatusReply { value: value };
            drtioaux::hw::send_link(0, &reply).unwrap();
        },

        drtioaux::Packet::I2cStartRequest { busno } => {
            let succeeded = i2c::start(busno).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::I2cRestartRequest { busno } => {
            let succeeded = i2c::restart(busno).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::I2cStopRequest { busno } => {
            let succeeded = i2c::stop(busno).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::I2cWriteRequest { busno, data } => {
            match i2c::write(busno, data) {
                Ok(ack) => drtioaux::hw::send_link(0, &drtioaux::Packet::I2cWriteReply { succeeded: true, ack: ack }).unwrap(),
                Err(_) => drtioaux::hw::send_link(0, &drtioaux::Packet::I2cWriteReply { succeeded: false, ack: false }).unwrap()
            };
        }
        drtioaux::Packet::I2cReadRequest { busno, ack } => {
            match i2c::read(busno, ack) {
                Ok(data) => drtioaux::hw::send_link(0, &drtioaux::Packet::I2cReadReply { succeeded: true, data: data }).unwrap(),
                Err(_) => drtioaux::hw::send_link(0, &drtioaux::Packet::I2cReadReply { succeeded: false, data: 0xff }).unwrap()
            };
        }

        drtioaux::Packet::SpiSetConfigRequest { busno, flags, write_div, read_div } => {
            let succeeded = spi::set_config(busno, flags, write_div, read_div).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::SpiBasicReply { succeeded: succeeded }).unwrap();
        },
        drtioaux::Packet::SpiSetXferRequest { busno, chip_select, write_length, read_length } => {
            let succeeded = spi::set_xfer(busno, chip_select, write_length, read_length).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::SpiBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::SpiWriteRequest { busno, data } => {
            let succeeded = spi::write(busno, data).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::SpiBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::SpiReadRequest { busno } => {
            match spi::read(busno) {
                Ok(data) => drtioaux::hw::send_link(0, &drtioaux::Packet::SpiReadReply { succeeded: true, data: data }).unwrap(),
                Err(_) => drtioaux::hw::send_link(0, &drtioaux::Packet::SpiReadReply { succeeded: false, data: 0 }).unwrap()
            };
        }

        _ => warn!("received unexpected aux packet {:?}", p)
    }
}

fn process_aux_packets() {
    let pr = drtioaux::hw::recv_link(0);
    match pr {
        Ok(None) => (),
        Ok(Some(p)) => process_aux_packet(&p),
        Err(e) => warn!("aux packet error ({})", e)
    }
}


fn process_errors() {
    let errors;
    unsafe {
        errors = (csr::DRTIO[0].protocol_error_read)();
        (csr::DRTIO[0].protocol_error_write)(errors);
    }
    if errors & 1 != 0 {
        error!("received packet of an unknown type");
    }
    if errors & 2 != 0 {
        error!("received truncated packet");
    }
    if errors & 4 != 0 {
        error!("write underflow");
    }
    if errors & 8 != 0 {
        error!("write overflow");
    }
}

#[cfg(rtio_frequency = "150.0")]
const SI5324_SETTINGS: si5324::FrequencySettings
        = si5324::FrequencySettings {
    n1_hs  : 9,
    nc1_ls : 4,
    n2_hs  : 10,
    n2_ls  : 33732,
    n31    : 9370,
    n32    : 7139,
    bwsel  : 3
};

fn drtio_link_is_up() -> bool {
    unsafe {
        (csr::DRTIO[0].link_status_read)() == 1
    }
}

fn startup() {
    board::clock::init();
    info!("ARTIQ satellite manager starting...");
    info!("software version {}", include_str!(concat!(env!("OUT_DIR"), "/git-describe")));
    info!("gateware version {}", board::ident::read(&mut [0; 64]));

    #[cfg(has_serwb_phy_amc)]
    serwb::wait_init();

    #[cfg(has_hmc830_7043)]
    hmc830_7043::init().expect("cannot initialize HMC830/7043");
    i2c::init();
    si5324::setup(&SI5324_SETTINGS).expect("cannot initialize Si5324");

    loop {
        while !drtio_link_is_up() {
            process_errors();
        }
        info!("link is up, switching to recovered clock");
        si5324::select_ext_input(true).expect("failed to switch clocks");
        while drtio_link_is_up() {
            process_errors();
            process_aux_packets();
        }
        info!("link is down, switching to local crystal clock");
        si5324::select_ext_input(false).expect("failed to switch clocks");
    }
}

#[global_allocator]
static mut ALLOC: alloc_list::ListAlloc = alloc_list::EMPTY;

#[no_mangle]
pub extern fn main() -> i32 {
    unsafe {
        extern {
            static mut _fheap: u8;
            static mut _eheap: u8;
        }
        ALLOC.add_range(&mut _fheap, &mut _eheap);

        static mut LOG_BUFFER: [u8; 65536] = [0; 65536];
        logger_artiq::BufferLogger::new(&mut LOG_BUFFER[..]).register(startup);
        0
    }
}

#[no_mangle]
pub extern fn exception(vect: u32, _regs: *const u32, pc: u32, ea: u32) {
    panic!("exception {:?} at PC 0x{:x}, EA 0x{:x}", vect, pc, ea)
}

#[no_mangle]
pub extern fn abort() {
    println!("aborted");
    loop {}
}

#[no_mangle]
#[lang = "panic_fmt"]
pub extern fn panic_fmt(args: core::fmt::Arguments, file: &'static str, line: u32) -> ! {
    println!("panic at {}:{}: {}", file, line, args);
    loop {}
}

// Allow linking with crates that are built as -Cpanic=unwind even if we use -Cpanic=abort.
// This is never called.
#[allow(non_snake_case)]
#[no_mangle]
pub extern "C" fn _Unwind_Resume() -> ! {
    loop {}
}
