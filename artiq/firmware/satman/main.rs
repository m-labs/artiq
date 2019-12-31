#![feature(never_type, panic_implementation, panic_info_message, const_slice_len, try_from)]
#![no_std]

#[macro_use]
extern crate log;
#[macro_use]
extern crate board_misoc;
extern crate board_artiq;

use core::convert::TryFrom;
use board_misoc::{csr, irq, ident, clock, uart_logger, i2c};
#[cfg(has_si5324)]
use board_artiq::si5324;
#[cfg(has_wrpll)]
use board_artiq::wrpll;
use board_artiq::{spi, drtioaux};
use board_artiq::drtio_routing;
#[cfg(has_hmc830_7043)]
use board_artiq::hmc830_7043;

mod repeater;
#[cfg(has_jdcg)]
mod jdcg;
#[cfg(any(has_ad9154, has_jdcg))]
pub mod jdac_requests;

fn drtiosat_reset(reset: bool) {
    unsafe {
        csr::drtiosat::reset_write(if reset { 1 } else { 0 });
    }
}

fn drtiosat_reset_phy(reset: bool) {
    unsafe {
        csr::drtiosat::reset_phy_write(if reset { 1 } else { 0 });
    }
}

fn drtiosat_link_rx_up() -> bool {
    unsafe {
        csr::drtiosat::rx_up_read() == 1
    }
}

fn drtiosat_tsc_loaded() -> bool {
    unsafe {
        let tsc_loaded = csr::drtiosat::tsc_loaded_read() == 1;
        if tsc_loaded {
            csr::drtiosat::tsc_loaded_write(1);
        }
        tsc_loaded
    }
}


#[cfg(has_drtio_routing)]
macro_rules! forward {
    ($routing_table:expr, $destination:expr, $rank:expr, $repeaters:expr, $packet:expr) => {{
        let hop = $routing_table.0[$destination as usize][$rank as usize];
        if hop != 0 {
            let repno = (hop - 1) as usize;
            if repno < $repeaters.len() {
                return $repeaters[repno].aux_forward($packet);
            } else {
                return Err(drtioaux::Error::RoutingError);
            }
        }
    }}
}

#[cfg(not(has_drtio_routing))]
macro_rules! forward {
    ($routing_table:expr, $destination:expr, $rank:expr, $repeaters:expr, $packet:expr) => {}
}

fn process_aux_packet(_repeaters: &mut [repeater::Repeater],
        _routing_table: &mut drtio_routing::RoutingTable, _rank: &mut u8,
        packet: drtioaux::Packet) -> Result<(), drtioaux::Error<!>> {
    // In the code below, *_chan_sel_write takes an u8 if there are fewer than 256 channels,
    // and u16 otherwise; hence the `as _` conversion.
    match packet {
        drtioaux::Packet::EchoRequest =>
            drtioaux::send(0, &drtioaux::Packet::EchoReply),
        drtioaux::Packet::ResetRequest => {
            info!("resetting RTIO");
            drtiosat_reset(true);
            clock::spin_us(100);
            drtiosat_reset(false);
            for rep in _repeaters.iter() {
                if let Err(e) = rep.rtio_reset() {
                    error!("failed to issue RTIO reset ({})", e);
                }
            }
            drtioaux::send(0, &drtioaux::Packet::ResetAck)
        },

        drtioaux::Packet::DestinationStatusRequest { destination: _destination } => {
            #[cfg(has_drtio_routing)]
            let hop = _routing_table.0[_destination as usize][*_rank as usize];
            #[cfg(not(has_drtio_routing))]
            let hop = 0;

            if hop == 0 {
                let errors;
                unsafe {
                    errors = csr::drtiosat::rtio_error_read();
                }
                if errors & 1 != 0 {
                    let channel;
                    unsafe {
                        channel = csr::drtiosat::sequence_error_channel_read();
                        csr::drtiosat::rtio_error_write(1);
                    }
                    drtioaux::send(0,
                        &drtioaux::Packet::DestinationSequenceErrorReply { channel })?;
                } else if errors & 2 != 0 {
                    let channel;
                    unsafe {
                        channel = csr::drtiosat::collision_channel_read();
                        csr::drtiosat::rtio_error_write(2);
                    }
                    drtioaux::send(0,
                        &drtioaux::Packet::DestinationCollisionReply { channel })?;
                } else if errors & 4 != 0 {
                    let channel;
                    unsafe {
                        channel = csr::drtiosat::busy_channel_read();
                        csr::drtiosat::rtio_error_write(4);
                    }
                    drtioaux::send(0,
                        &drtioaux::Packet::DestinationBusyReply { channel })?;
                }
                else {
                    drtioaux::send(0, &drtioaux::Packet::DestinationOkReply)?;
                }
            }

            #[cfg(has_drtio_routing)]
            {
                if hop != 0 {
                    let hop = hop as usize;
                    if hop <= csr::DRTIOREP.len() {
                        let repno = hop - 1;
                        match _repeaters[repno].aux_forward(&drtioaux::Packet::DestinationStatusRequest {
                            destination: _destination
                        }) {
                            Ok(()) => (),
                            Err(drtioaux::Error::LinkDown) => drtioaux::send(0, &drtioaux::Packet::DestinationDownReply)?,
                            Err(e) => {
                                drtioaux::send(0, &drtioaux::Packet::DestinationDownReply)?;
                                error!("aux error when handling destination status request: {}", e);
                            },
                        }
                    } else {
                        drtioaux::send(0, &drtioaux::Packet::DestinationDownReply)?;
                    }
                }
            }

            Ok(())
        }

        #[cfg(has_drtio_routing)]
        drtioaux::Packet::RoutingSetPath { destination, hops } => {
            _routing_table.0[destination as usize] = hops;
            for rep in _repeaters.iter() {
                if let Err(e) = rep.set_path(destination, &hops) {
                    error!("failed to set path ({})", e);
                }
            }
            drtioaux::send(0, &drtioaux::Packet::RoutingAck)
        }
        #[cfg(has_drtio_routing)]
        drtioaux::Packet::RoutingSetRank { rank } => {
            *_rank = rank;
            drtio_routing::interconnect_enable_all(_routing_table, rank);

            let rep_rank = rank + 1;
            for rep in _repeaters.iter() {
                if let Err(e) = rep.set_rank(rep_rank) {
                    error!("failed to set rank ({})", e);
                }
            }

            info!("rank: {}", rank);
            info!("routing table: {}", _routing_table);

            drtioaux::send(0, &drtioaux::Packet::RoutingAck)
        }

        #[cfg(not(has_drtio_routing))]
        drtioaux::Packet::RoutingSetPath { destination: _, hops: _ } => {
            drtioaux::send(0, &drtioaux::Packet::RoutingAck)
        }
        #[cfg(not(has_drtio_routing))]
        drtioaux::Packet::RoutingSetRank { rank: _ } => {
            drtioaux::send(0, &drtioaux::Packet::RoutingAck)
        }

        drtioaux::Packet::MonitorRequest { destination: _destination, channel, probe } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
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
            drtioaux::send(0, &reply)
        },
        drtioaux::Packet::InjectionRequest { destination: _destination, channel, overrd, value } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            #[cfg(has_rtio_moninj)]
            unsafe {
                csr::rtio_moninj::inj_chan_sel_write(channel as _);
                csr::rtio_moninj::inj_override_sel_write(overrd);
                csr::rtio_moninj::inj_value_write(value);
            }
            Ok(())
        },
        drtioaux::Packet::InjectionStatusRequest { destination: _destination, channel, overrd } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
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
            drtioaux::send(0, &drtioaux::Packet::InjectionStatusReply { value: value })
        },

        drtioaux::Packet::I2cStartRequest { destination: _destination, busno } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let succeeded = i2c::start(busno).is_ok();
            drtioaux::send(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded })
        }
        drtioaux::Packet::I2cRestartRequest { destination: _destination, busno } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let succeeded = i2c::restart(busno).is_ok();
            drtioaux::send(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded })
        }
        drtioaux::Packet::I2cStopRequest { destination: _destination, busno } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let succeeded = i2c::stop(busno).is_ok();
            drtioaux::send(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded })
        }
        drtioaux::Packet::I2cWriteRequest { destination: _destination, busno, data } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            match i2c::write(busno, data) {
                Ok(ack) => drtioaux::send(0,
                    &drtioaux::Packet::I2cWriteReply { succeeded: true, ack: ack }),
                Err(_) => drtioaux::send(0,
                    &drtioaux::Packet::I2cWriteReply { succeeded: false, ack: false })
            }
        }
        drtioaux::Packet::I2cReadRequest { destination: _destination, busno, ack } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            match i2c::read(busno, ack) {
                Ok(data) => drtioaux::send(0,
                    &drtioaux::Packet::I2cReadReply { succeeded: true, data: data }),
                Err(_) => drtioaux::send(0,
                    &drtioaux::Packet::I2cReadReply { succeeded: false, data: 0xff })
            }
        }

        drtioaux::Packet::SpiSetConfigRequest { destination: _destination, busno, flags, length, div, cs } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let succeeded = spi::set_config(busno, flags, length, div, cs).is_ok();
            drtioaux::send(0,
                &drtioaux::Packet::SpiBasicReply { succeeded: succeeded })
        },
        drtioaux::Packet::SpiWriteRequest { destination: _destination, busno, data } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let succeeded = spi::write(busno, data).is_ok();
            drtioaux::send(0,
                &drtioaux::Packet::SpiBasicReply { succeeded: succeeded })
        }
        drtioaux::Packet::SpiReadRequest { destination: _destination, busno } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            match spi::read(busno) {
                Ok(data) => drtioaux::send(0,
                    &drtioaux::Packet::SpiReadReply { succeeded: true, data: data }),
                Err(_) => drtioaux::send(0,
                    &drtioaux::Packet::SpiReadReply { succeeded: false, data: 0 })
            }
        }

        drtioaux::Packet::JdacBasicRequest { destination: _destination, dacno: _dacno,
                                             reqno: _reqno, param: _param } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            #[cfg(has_ad9154)]
            let (succeeded, retval) = {
                #[cfg(rtio_frequency = "125.0")]
                const LINERATE: u64 = 5_000_000_000;
                #[cfg(rtio_frequency = "150.0")]
                const LINERATE: u64 = 6_000_000_000;
                match _reqno {
                    jdac_requests::INIT => (board_artiq::ad9154::setup(_dacno, LINERATE).is_ok(), 0),
                    jdac_requests::PRINT_STATUS => { board_artiq::ad9154::status(_dacno); (true, 0) },
                    jdac_requests::PRBS => (board_artiq::ad9154::prbs(_dacno).is_ok(), 0),
                    jdac_requests::STPL => (board_artiq::ad9154::stpl(_dacno, 4, 2).is_ok(), 0),
                    jdac_requests::SYSREF_DELAY_DAC => { board_artiq::hmc830_7043::hmc7043::sysref_delay_dac(_dacno, _param); (true, 0) },
                    jdac_requests::SYSREF_SLIP => { board_artiq::hmc830_7043::hmc7043::sysref_slip(); (true, 0) },
                    jdac_requests::SYNC => {
                        match board_artiq::ad9154::sync(_dacno) {
                            Ok(false) => (true, 0),
                            Ok(true) => (true, 1),
                            Err(e) => {
                                error!("DAC sync failed: {}", e);
                                (false, 0)
                            }
                        }
                    }
                    _ => (false, 0)
                }
            };
            #[cfg(not(has_ad9154))]
            let (succeeded, retval) = (false, 0);
            drtioaux::send(0,
                &drtioaux::Packet::JdacBasicReply { succeeded: succeeded, retval: retval })
        }

        _ => {
            warn!("received unexpected aux packet");
            Ok(())
        }
    }
}

fn process_aux_packets(repeaters: &mut [repeater::Repeater],
        routing_table: &mut drtio_routing::RoutingTable, rank: &mut u8) {
    let result =
        drtioaux::recv(0).and_then(|packet| {
            if let Some(packet) = packet {
                process_aux_packet(repeaters, routing_table, rank, packet)
            } else {
                Ok(())
            }
        });
    match result {
        Ok(()) => (),
        Err(e) => warn!("aux packet error ({})", e)
    }
}

fn drtiosat_process_errors() {
    let errors;
    unsafe {
        errors = csr::drtiosat::protocol_error_read();
    }
    if errors & 1 != 0 {
        error!("received packet of an unknown type");
    }
    if errors & 2 != 0 {
        error!("received truncated packet");
    }
    if errors & 4 != 0 {
        let destination;
        unsafe {
            destination = csr::drtiosat::buffer_space_timeout_dest_read();
        }
        error!("timeout attempting to get buffer space from CRI, destination=0x{:02x}", destination)
    }
    if errors & 8 != 0 {
        let channel;
        let timestamp_event;
        let timestamp_counter;
        unsafe {
            channel = csr::drtiosat::underflow_channel_read();
            timestamp_event = csr::drtiosat::underflow_timestamp_event_read() as i64;
            timestamp_counter = csr::drtiosat::underflow_timestamp_counter_read() as i64;
        }
        error!("write underflow, channel={}, timestamp={}, counter={}, slack={}",
               channel, timestamp_event, timestamp_counter, timestamp_event-timestamp_counter);
    }
    if errors & 16 != 0 {
        error!("write overflow");
    }
    unsafe {
        csr::drtiosat::protocol_error_write(errors);
    }
}


#[cfg(has_rtio_crg)]
fn init_rtio_crg() {
    unsafe {
        csr::rtio_crg::pll_reset_write(0);
    }
    clock::spin_us(150);
    let locked = unsafe { csr::rtio_crg::pll_locked_read() != 0 };
    if !locked {
        error!("RTIO clock failed");
    }
}

#[cfg(not(has_rtio_crg))]
fn init_rtio_crg() { }

fn hardware_tick(ts: &mut u64) {
    let now = clock::get_ms();
    if now > *ts {
        #[cfg(has_grabber)]
        board_artiq::grabber::tick();
        *ts = now + 200;
    }
}

#[cfg(all(has_si5324, rtio_frequency = "150.0"))]
const SI5324_SETTINGS: si5324::FrequencySettings
    = si5324::FrequencySettings {
    n1_hs  : 6,
    nc1_ls : 6,
    n2_hs  : 10,
    n2_ls  : 270,
    n31    : 75,
    n32    : 75,
    bwsel  : 4,
    crystal_ref: true
};

#[cfg(all(has_si5324, rtio_frequency = "125.0"))]
const SI5324_SETTINGS: si5324::FrequencySettings
    = si5324::FrequencySettings {
    n1_hs  : 5,
    nc1_ls : 8,
    n2_hs  : 7,
    n2_ls  : 360,
    n31    : 63,
    n32    : 63,
    bwsel  : 4,
    crystal_ref: true
};

#[no_mangle]
pub extern fn main() -> i32 {
    clock::init();
    uart_logger::ConsoleLogger::register();

    info!("ARTIQ satellite manager starting...");
    info!("software ident {}", csr::CONFIG_IDENTIFIER_STR);
    info!("gateware ident {}", ident::read(&mut [0; 64]));

    #[cfg(has_si5324)]
    {
        i2c::init().expect("I2C initialization failed");
        si5324::setup(&SI5324_SETTINGS, si5324::Input::Ckin1).expect("cannot initialize Si5324");
    }
    #[cfg(has_wrpll)]
    wrpll::init();
    unsafe {
        csr::drtio_transceiver::stable_clkin_write(1);
    }
    clock::spin_us(1500); // wait for CPLL/QPLL lock
    #[cfg(has_wrpll)]
    wrpll::diagnostics();
    init_rtio_crg();

    #[cfg(has_hmc830_7043)]
    /* must be the first SPI init because of HMC830 SPI mode selection */
    hmc830_7043::init().expect("cannot initialize HMC830/7043");
    #[cfg(has_ad9154)]
    {
        for dacno in 0..csr::CONFIG_AD9154_COUNT {
            board_artiq::ad9154::reset_and_detect(dacno as u8).expect("AD9154 DAC not detected");
        }
    }

    #[cfg(has_drtio_routing)]
    let mut repeaters = [repeater::Repeater::default(); csr::DRTIOREP.len()];
    #[cfg(not(has_drtio_routing))]
    let mut repeaters = [repeater::Repeater::default(); 0];
    for i in 0..repeaters.len() {
        repeaters[i] = repeater::Repeater::new(i as u8);
    } 
    let mut routing_table = drtio_routing::RoutingTable::default_empty();
    let mut rank = 1;

    let mut hardware_tick_ts = 0;

    loop {
        while !drtiosat_link_rx_up() {
            drtiosat_process_errors();
            for mut rep in repeaters.iter_mut() {
                rep.service(&routing_table, rank);
            }
            hardware_tick(&mut hardware_tick_ts);
        }

        info!("uplink is up, switching to recovered clock");
        #[cfg(has_si5324)]
        {
            si5324::siphaser::select_recovered_clock(true).expect("failed to switch clocks");
            si5324::siphaser::calibrate_skew().expect("failed to calibrate skew");
        }
        #[cfg(has_wrpll)]
        wrpll::select_recovered_clock(true);

        #[cfg(has_jdcg)]
        {
            /*
             * One side of the JESD204 elastic buffer is clocked by the Si5324, the other
             * by the RTM.
             * The elastic buffer can operate only when those two clocks are derived from
             * the same oscillator.
             * This is the case when either of those conditions is true:
             * (1) The DRTIO master and the RTM are clocked directly from a common external
             *     source, *and* the Si5324 has locked to the recovered clock.
             *     This clocking scheme provides less noise and phase drift at the DACs.
             * (2) The RTM clock is connected to the Si5324 output.
             * To handle those cases, we simply keep the JESD204 core in reset unless the
             * Si5324 is locked to the recovered clock.
             */
            jdcg::jesd::reset(false);
            if repeaters[0].is_up() {
                let _ = jdcg::jdac::init();
            }
        }

        drtioaux::reset(0);
        drtiosat_reset(false);
        drtiosat_reset_phy(false);

        #[cfg(has_jdcg)]
        let mut rep0_was_up = repeaters[0].is_up();
        while drtiosat_link_rx_up() {
            drtiosat_process_errors();
            process_aux_packets(&mut repeaters, &mut routing_table, &mut rank);
            for mut rep in repeaters.iter_mut() {
                rep.service(&routing_table, rank);
            }
            hardware_tick(&mut hardware_tick_ts);
            if drtiosat_tsc_loaded() {
                info!("TSC loaded from uplink");
                #[cfg(has_jdcg)]
                {
                    if rep0_was_up {
                        jdcg::jesd204sync::sysref_auto_align();
                    }
                }
                for rep in repeaters.iter() {
                    if let Err(e) = rep.sync_tsc() {
                        error!("failed to sync TSC ({})", e);
                    }
                }
                if let Err(e) = drtioaux::send(0, &drtioaux::Packet::TSCAck) {
                    error!("aux packet error: {}", e);
                }
            }
            #[cfg(has_jdcg)]
            {
                let rep0_is_up = repeaters[0].is_up();
                if rep0_is_up && !rep0_was_up {
                    let _ = jdcg::jdac::init();
                    jdcg::jesd204sync::sysref_auto_align();
                }
                rep0_was_up = rep0_is_up;
            }
        }

        #[cfg(has_jdcg)]
        jdcg::jesd::reset(true);

        drtiosat_reset_phy(true);
        drtiosat_reset(true);
        drtiosat_tsc_loaded();
        info!("uplink is down, switching to local oscillator clock");
        #[cfg(has_si5324)]
        si5324::siphaser::select_recovered_clock(false).expect("failed to switch clocks");
        #[cfg(has_wrpll)]
        wrpll::select_recovered_clock(false);
    }
}

#[no_mangle]
pub extern fn exception(vect: u32, _regs: *const u32, pc: u32, ea: u32) {
    let vect = irq::Exception::try_from(vect).expect("unknown exception");

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

#[no_mangle]
pub extern fn abort() {
    println!("aborted");
    loop {}
}

#[no_mangle] // https://github.com/rust-lang/rust/issues/{38281,51647}
#[panic_implementation]
pub fn panic_fmt(info: &core::panic::PanicInfo) -> ! {
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
    loop {}
}
