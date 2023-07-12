#![feature(never_type, panic_info_message, llvm_asm, default_alloc_error_handler)]
#![no_std]

#[macro_use]
extern crate log;
#[macro_use]
extern crate board_misoc;
extern crate board_artiq;
extern crate riscv;
extern crate alloc;
extern crate proto_artiq;

use core::convert::TryFrom;
use board_misoc::{csr, ident, clock, config, uart_logger, i2c, pmp};
#[cfg(has_si5324)]
use board_artiq::si5324;
use board_artiq::{spi, drtioaux};
use board_artiq::drtio_routing;
use proto_artiq::drtioaux_proto::ANALYZER_MAX_SIZE;
use board_artiq::drtio_eem;
use riscv::register::{mcause, mepc, mtval};
use dma::Manager as DmaManager;
use analyzer::Analyzer;

#[global_allocator]
static mut ALLOC: alloc_list::ListAlloc = alloc_list::EMPTY;

mod repeater;
mod dma;
mod analyzer;

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

fn process_aux_packet(_manager: &mut DmaManager, analyzer: &mut Analyzer, _repeaters: &mut [repeater::Repeater],
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
                value = csr::rtio_moninj::mon_value_read() as u64;
            }
            #[cfg(not(has_rtio_moninj))]
            {
                value = 0;
            }
            let reply = drtioaux::Packet::MonitorReply { value: value };
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
        drtioaux::Packet::I2cSwitchSelectRequest { destination: _destination, busno, address, mask } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let succeeded = i2c::switch_select(busno, address, mask).is_ok();
            drtioaux::send(0, &drtioaux::Packet::I2cBasicReply { succeeded: succeeded })
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

        drtioaux::Packet::AnalyzerHeaderRequest { destination: _destination } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let header = analyzer.get_header();
            drtioaux::send(0, &drtioaux::Packet::AnalyzerHeader {
                total_byte_count: header.total_byte_count,
                sent_bytes: header.sent_bytes,
                overflow_occurred: header.overflow,
            })
        }

        drtioaux::Packet::AnalyzerDataRequest { destination: _destination } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let mut data_slice: [u8; ANALYZER_MAX_SIZE] = [0; ANALYZER_MAX_SIZE];
            let meta = analyzer.get_data(&mut data_slice);
            drtioaux::send(0, &drtioaux::Packet::AnalyzerData {
                last: meta.last,
                length: meta.len,
                data: data_slice,
            })
        }

        #[cfg(has_rtio_dma)]
        drtioaux::Packet::DmaAddTraceRequest { destination: _destination, id, last, length, trace } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let succeeded = _manager.add(id, last, &trace, length as usize).is_ok();
            drtioaux::send(0,
                &drtioaux::Packet::DmaAddTraceReply { succeeded: succeeded })
        }
        #[cfg(has_rtio_dma)]
        drtioaux::Packet::DmaRemoveTraceRequest { destination: _destination, id } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let succeeded = _manager.erase(id).is_ok();
            drtioaux::send(0,
                &drtioaux::Packet::DmaRemoveTraceReply { succeeded: succeeded })
        }
        #[cfg(has_rtio_dma)]
        drtioaux::Packet::DmaPlaybackRequest { destination: _destination, id, timestamp } => {
            forward!(_routing_table, _destination, *_rank, _repeaters, &packet);
            let succeeded = _manager.playback(id, timestamp).is_ok();
            drtioaux::send(0,
                &drtioaux::Packet::DmaPlaybackReply { succeeded: succeeded })
        }

        _ => {
            warn!("received unexpected aux packet");
            Ok(())
        }
    }
}

fn process_aux_packets(dma_manager: &mut DmaManager, analyzer: &mut Analyzer,
        repeaters: &mut [repeater::Repeater],
        routing_table: &mut drtio_routing::RoutingTable, rank: &mut u8) {
    let result =
        drtioaux::recv(0).and_then(|packet| {
            if let Some(packet) = packet {
                process_aux_packet(dma_manager, analyzer, repeaters, routing_table, rank, packet)
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
    crystal_as_ckin2: true
};

#[cfg(all(has_si5324, rtio_frequency = "100.0"))]
const SI5324_SETTINGS: si5324::FrequencySettings
    = si5324::FrequencySettings {
    n1_hs  : 5,
    nc1_ls : 10,
    n2_hs  : 10,
    n2_ls  : 250,
    n31    : 50,
    n32    : 50,
    bwsel  : 4,
    crystal_as_ckin2: true
};

#[cfg(not(soc_platform = "efc"))]
fn sysclk_setup() {
    let switched = unsafe {
        csr::crg::switch_done_read()
    };
    if switched == 1 {
        info!("Clocking has already been set up.");
        return;
    }
    else {
        #[cfg(has_si5324)]
        si5324::setup(&SI5324_SETTINGS, si5324::Input::Ckin1).expect("cannot initialize Si5324");
        info!("Switching sys clock, rebooting...");
        // delay for clean UART log, wait until UART FIFO is empty
        clock::spin_us(1300);
        unsafe {
            csr::drtio_transceiver::stable_clkin_write(1);
        }
        loop {}
    }
}


#[cfg(soc_platform = "efc")]
fn sysclk_setup() -> board_misoc::io_expander::IoExpander {
    let mut io_expander = board_misoc::io_expander::IoExpander::new().unwrap();

    // Avoid setting up clock before the master clock is stable
    unsafe {
        while csr::eem_transceiver::aux_mst_clk_rdy_in_read() == 0 {
            clock::spin_us(1_000_000);
            println!("Master clock not ready...");
        }
    }
    println!("Master clock ready!");

    // Skip intialization if it had reset
    if (unsafe { csr::crg::had_clk_switch_read() } != 0) {
        io_expander.set(0, 3, false);
        io_expander.set(0, 2, true);
        return io_expander;
    }

    io_expander.init().expect("I2C I/O expander #0 initialization failed");

    // Latch in the logic signal before enabling
    io_expander.set(0, 3, false);
    io_expander.set(0, 2, true);
    io_expander.service().unwrap();
    println!("Serviced I/O expander.");

    // Changing output direction of the I/O expander
    // will immediately update clock source, which may trigger reboot
    // So, notify the gateware a clock switch request in advance
    unsafe {
        csr::crg::switched_clk_write(1);
    }
    io_expander.set_oe(0, 1 << 2 | 1 << 3);

    loop {}

    unreachable!()
}


#[no_mangle]
pub extern fn main() -> i32 {
    extern {
        static mut _fheap: u8;
        static mut _eheap: u8;
        static mut _sstack_guard: u8;
    }

    unsafe {
        ALLOC.add_range(&mut _fheap, &mut _eheap);
        pmp::init_stack_guard(&_sstack_guard as *const u8 as usize);
    }

    clock::init();
    uart_logger::ConsoleLogger::register();

    info!("ARTIQ satellite manager starting...");
    info!("software ident {}", csr::CONFIG_IDENTIFIER_STR);
    info!("gateware ident {}", ident::read(&mut [0; 64]));

    #[cfg(has_i2c)]
    i2c::init().expect("I2C initialization failed");
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

    #[cfg(not(soc_platform = "efc"))]
    sysclk_setup();

    #[cfg(soc_platform = "efc")]
    let mut io_expander = sysclk_setup();

    #[cfg(soc_platform = "efc")]
    {
        // Do whatever we need the IO expander to do here
        // The CLK_SELs must be output to keep MMCX
        io_expander.set_oe(0, 1 << 2 | 1 << 3 | 1 << 5 | 1 << 6 | 1 << 7).unwrap();
        io_expander.set_oe(1, 1 << 1).unwrap();

        io_expander.set(0, 5, true);
        io_expander.set(0, 6, true);
        io_expander.set(0, 7, true);
        io_expander.set(1, 1, true);

        io_expander.service().unwrap();
    }

    unsafe {
        csr::drtio_transceiver::txenable_write(0xffffffffu32 as _);
    }

    init_rtio_crg();

    unsafe {
        csr::eem_transceiver::aux_sat_clk_rdy_out_write(1);
        while csr::eem_transceiver::aux_phase_rdy_in_read() == 0 {
            println!("phase aligning...");
            clock::spin_us(1_000_000);
        }
        println!("phase aligned!");
        clock::spin_us(1_000_000);

        // Perform EEM aligning if not configured
        config::read("master_delay", |r| {
            match r {
                Ok(record) => {
                    println!("recorded delay: {:#?}", &*(record.as_ptr() as *const drtio_eem::SerdesConfig));
                    drtio_eem::write_config(&*(record.as_ptr() as *const drtio_eem::SerdesConfig));
                    csr::eem_transceiver::serdes_send_align_write(0);
                    csr::eem_transceiver::rx_ready_write(1);
                    println!("satellite ready");
                },

                Err(_) => {
                    // Alignment complete, start sending comma to master
                    csr::eem_transceiver::serdes_send_align_write(1);
                    clock::spin_us(100);
            
                    let master_config = drtio_eem::align_eem();
                    drtio_eem::write_config(&master_config);
            
                    csr::eem_transceiver::aux_align_mst_out_write(1);
            
                    // Re-enable normal traffic
                    while csr::eem_transceiver::aux_align_sat_in_read() == 0 {
                        println!("master aligning...");
                        clock::spin_us(1_000_000);
                    }
                    csr::eem_transceiver::serdes_send_align_write(0);
                    csr::eem_transceiver::rx_ready_write(1);

                    config::write("master_delay", master_config.as_bytes());
                }
            }
        })
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
            for rep in repeaters.iter_mut() {
                rep.service(&routing_table, rank);
            }
            #[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
            {
                io_expander0.service().expect("I2C I/O expander #0 service failed");
                io_expander1.service().expect("I2C I/O expander #1 service failed");
            }
            hardware_tick(&mut hardware_tick_ts);
        }

        info!("uplink is up, switching to recovered clock");
        #[cfg(has_si5324)]
        {
            si5324::siphaser::select_recovered_clock(true).expect("failed to switch clocks");
            si5324::siphaser::calibrate_skew().expect("failed to calibrate skew");
        }

        // DMA manager created here, so when link is dropped, all DMA traces
        // are cleared out for a clean slate on subsequent connections,
        // without a manual intervention.
        let mut dma_manager = DmaManager::new();

        // Reset the analyzer as well.
        let mut analyzer = Analyzer::new();

        drtioaux::reset(0);
        drtiosat_reset(false);
        drtiosat_reset_phy(false);

        while drtiosat_link_rx_up() {
            drtiosat_process_errors();
            process_aux_packets(&mut dma_manager, &mut analyzer, &mut repeaters, &mut routing_table, &mut rank);
            for rep in repeaters.iter_mut() {
                rep.service(&routing_table, rank);
            }
            #[cfg(all(soc_platform = "kasli", hw_rev = "v2.0"))]
            {
                io_expander0.service().expect("I2C I/O expander #0 service failed");
                io_expander1.service().expect("I2C I/O expander #1 service failed");
            }
            hardware_tick(&mut hardware_tick_ts);
            if drtiosat_tsc_loaded() {
                info!("TSC loaded from uplink");
                for rep in repeaters.iter() {
                    if let Err(e) = rep.sync_tsc() {
                        error!("failed to sync TSC ({})", e);
                    }
                }
                if let Err(e) = drtioaux::send(0, &drtioaux::Packet::TSCAck) {
                    error!("aux packet error: {}", e);
                }
            }
            if let Some(status) = dma_manager.check_state() {
                info!("playback done, error: {}, channel: {}, timestamp: {}", status.error, status.channel, status.timestamp);
                if let Err(e) = drtioaux::send(0, &drtioaux::Packet::DmaPlaybackStatus { 
                    destination: rank, id: status.id, error: status.error, channel: status.channel, timestamp: status.timestamp }) {
                    error!("error sending DMA playback status: {}", e);
                }
            }
        }

        drtiosat_reset_phy(true);
        drtiosat_reset(true);
        drtiosat_tsc_loaded();
        info!("uplink is down, switching to local oscillator clock");
        #[cfg(has_si5324)]
        si5324::siphaser::select_recovered_clock(false).expect("failed to switch clocks");
    }
}

#[no_mangle]
pub extern fn exception(_regs: *const u32) {
    let pc = mepc::read();
    let cause = mcause::read().cause();
    
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
    panic!("exception {:?} at PC 0x{:x}, trap value 0x{:x}", cause, u32::try_from(pc).unwrap(), mtval)
}

#[no_mangle]
pub extern fn abort() {
    println!("aborted");
    loop {}
}

#[no_mangle] // https://github.com/rust-lang/rust/issues/{38281,51647}
#[panic_handler]
pub fn panic_fmt(info: &core::panic::PanicInfo) -> ! {
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
    loop {}
}
