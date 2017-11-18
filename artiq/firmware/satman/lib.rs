#![feature(compiler_builtins_lib, lang_items)]
#![no_std]

extern crate compiler_builtins;
extern crate alloc_artiq;
extern crate std_artiq as std;
#[macro_use]
extern crate log;
extern crate logger_artiq;
#[macro_use]
extern crate board;
extern crate drtioaux;

fn process_aux_packet(p: &drtioaux::Packet) {
    // In the code below, *_chan_sel_write takes an u8 if there are fewer than 256 channels,
    // and u16 otherwise; hence the `as _` conversion.
    match *p {
        drtioaux::Packet::EchoRequest => drtioaux::hw::send_link(0, &drtioaux::Packet::EchoReply).unwrap(),

        drtioaux::Packet::RtioErrorRequest => {
            let errors;
            unsafe {
                errors = (board::csr::DRTIO[0].rtio_error_read)();
            }
            if errors & 1 != 0 {
                unsafe {
                    (board::csr::DRTIO[0].rtio_error_write)(1);
                }
                drtioaux::hw::send_link(0, &drtioaux::Packet::RtioErrorCollisionReply).unwrap();
            } else if errors & 2 != 0 {
                unsafe {
                    (board::csr::DRTIO[0].rtio_error_write)(2);
                }
                drtioaux::hw::send_link(0, &drtioaux::Packet::RtioErrorBusyReply).unwrap();
            } else {
                drtioaux::hw::send_link(0, &drtioaux::Packet::RtioNoErrorReply).unwrap();
            }
        }

        drtioaux::Packet::MonitorRequest { channel, probe } => {
            let value;
            #[cfg(has_rtio_moninj)]
            unsafe {
                board::csr::rtio_moninj::mon_chan_sel_write(channel as _);
                board::csr::rtio_moninj::mon_probe_sel_write(probe);
                board::csr::rtio_moninj::mon_value_update_write(1);
                value = board::csr::rtio_moninj::mon_value_read();
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
                board::csr::rtio_moninj::inj_chan_sel_write(channel as _);
                board::csr::rtio_moninj::inj_override_sel_write(overrd);
                board::csr::rtio_moninj::inj_value_write(value);
            }
        },
        drtioaux::Packet::InjectionStatusRequest { channel, overrd } => {
            let value;
            #[cfg(has_rtio_moninj)]
            unsafe {
                board::csr::rtio_moninj::inj_chan_sel_write(channel as _);
                board::csr::rtio_moninj::inj_override_sel_write(overrd);
                value = board::csr::rtio_moninj::inj_value_read();
            }
            #[cfg(not(has_rtio_moninj))]
            {
                value = 0;
            }
            let reply = drtioaux::Packet::InjectionStatusReply { value: value };
            drtioaux::hw::send_link(0, &reply).unwrap();
        },

        drtioaux::Packet::I2cStartRequest { busno } => {
            let succeeded = board::i2c::start(busno).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::I2cRestartRequest { busno } => {
            let succeeded = board::i2c::restart(busno).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::I2cStopRequest { busno } => {
            let succeeded = board::i2c::stop(busno).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::I2cWriteRequest { busno, data } => {
            match board::i2c::write(busno, data) {
                Ok(ack) => drtioaux::hw::send_link(0, &drtioaux::Packet::I2cWriteReply { succeeded: true, ack: ack }).unwrap(),
                Err(_) => drtioaux::hw::send_link(0, &drtioaux::Packet::I2cWriteReply { succeeded: false, ack: false }).unwrap()
            };
        }
        drtioaux::Packet::I2cReadRequest { busno, ack } => {
            match board::i2c::read(busno, ack) {
                Ok(data) => drtioaux::hw::send_link(0, &drtioaux::Packet::I2cReadReply { succeeded: true, data: data }).unwrap(),
                Err(_) => drtioaux::hw::send_link(0, &drtioaux::Packet::I2cReadReply { succeeded: false, data: 0xff }).unwrap()
            };
        }

        drtioaux::Packet::SpiSetConfigRequest { busno, flags, write_div, read_div } => {
            let succeeded = board::spi::set_config(busno, flags, write_div, read_div).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::SpiBasicReply { succeeded: succeeded }).unwrap();
        },
        drtioaux::Packet::SpiSetXferRequest { busno, chip_select, write_length, read_length } => {
            let succeeded = board::spi::set_xfer(busno, chip_select, write_length, read_length).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::SpiBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::SpiWriteRequest { busno, data } => {
            let succeeded = board::spi::write(busno, data).is_ok();
            drtioaux::hw::send_link(0, &drtioaux::Packet::SpiBasicReply { succeeded: succeeded }).unwrap();
        }
        drtioaux::Packet::SpiReadRequest { busno } => {
            match board::spi::read(busno) {
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
        errors = (board::csr::DRTIO[0].protocol_error_read)();
        (board::csr::DRTIO[0].protocol_error_write)(errors);
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
    if errors & 16 != 0 {
        error!("write sequence error");
    }
}


#[cfg(rtio_frequency = "62.5")]
const SI5324_SETTINGS: board::si5324::FrequencySettings
        = board::si5324::FrequencySettings {
    n1_hs  : 10,
    nc1_ls : 8,
    n2_hs  : 10,
    n2_ls  : 20112,
    n31    : 2514,
    n32    : 4597,
    bwsel  : 4
};

#[cfg(rtio_frequency = "150.0")]
const SI5324_SETTINGS: board::si5324::FrequencySettings
        = board::si5324::FrequencySettings {
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
        (board::csr::DRTIO[0].link_status_read)() == 1
    }
}

fn startup() {
    board::clock::init();
    info!("ARTIQ satellite manager starting...");
    info!("software version {}", include_str!(concat!(env!("OUT_DIR"), "/git-describe")));
    info!("gateware version {}", board::ident(&mut [0; 64]));

    #[cfg(has_serwb_phy_amc)]
    board::serwb::wait_init();

    #[cfg(has_ad9516)]
    board::ad9516::init().expect("cannot initialize AD9516");
    #[cfg(has_hmc830_7043)]
    board::hmc830_7043::init().expect("cannot initialize HMC830/7043");
    board::i2c::init();
    board::si5324::setup(&SI5324_SETTINGS).expect("cannot initialize Si5324");

    loop {
        while !drtio_link_is_up() {
            process_errors();
        }
        info!("link is up, switching to recovered clock");
        board::si5324::select_ext_input(true).expect("failed to switch clocks");
        while drtio_link_is_up() {
            process_errors();
            process_aux_packets();
        }
        info!("link is down, switching to local crystal clock");
        board::si5324::select_ext_input(false).expect("failed to switch clocks");
    }
}

#[no_mangle]
pub extern fn main() -> i32 {
    unsafe {
        extern {
            static mut _fheap: u8;
            static mut _eheap: u8;
        }
        alloc_artiq::seed(&mut _fheap as *mut u8,
                          &_eheap as *const u8 as usize - &_fheap as *const u8 as usize);

        static mut LOG_BUFFER: [u8; 65536] = [0; 65536];
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
    loop {}
}

// Allow linking with crates that are built as -Cpanic=unwind even if we use -Cpanic=abort.
// This is never called.
#[allow(non_snake_case)]
#[no_mangle]
pub extern "C" fn _Unwind_Resume() -> ! {
    loop {}
}
