#![no_std]
#![feature(lang_items)]

extern crate crc;
extern crate byteorder;
extern crate smoltcp;
#[macro_use]
extern crate board;

use core::{ptr, slice};
use crc::crc32;
use byteorder::{ByteOrder, BigEndian};
use board::{boot, cache};
#[cfg(has_ethmac)]
use board::{clock, config, ethmac};
use board::uart_console::Console;

fn check_integrity() -> bool {
    extern {
        static _begin: u8;
        static _end: u8;
        static _crc: u32;
    }

    unsafe {
        let length = &_end   as *const u8 as usize -
                     &_begin as *const u8 as usize;
        let bootloader = slice::from_raw_parts(&_begin as *const u8, length);
        crc32::checksum_ieee(bootloader) == _crc
    }
}

fn memory_test(total: &mut usize, wrong: &mut usize) -> bool {
    const MEMORY: *mut u32 = board::mem::MAIN_RAM_BASE as *mut u32;

    *total = 0;
    *wrong = 0;

    macro_rules! test {
        (
            $prepare:stmt;
            for $i:ident in ($range:expr) {
                MEMORY[$index:expr] = $data:expr
            }
        ) => ({
            $prepare;
            for $i in $range {
                unsafe { ptr::write_volatile(MEMORY.offset($index as isize), $data) };
                *total += 1;
            }

            cache::flush_cpu_dcache();
            cache::flush_l2_cache();

            $prepare;
            for $i in $range {
                if unsafe { ptr::read_volatile(MEMORY.offset($index as isize)) } != $data {
                    *wrong += 1;
                }
            }
        })
    }

    fn prng32(seed: &mut u32) -> u32 { *seed = 1664525 * *seed + 1013904223; *seed }
    fn prng16(seed: &mut u16) -> u16 { *seed = 25173 * *seed + 13849; *seed }

    // Test data bus
    test!((); for i in (0..0x100) { MEMORY[i] = 0xAAAAAAAA });
    test!((); for i in (0..0x100) { MEMORY[i] = 0x55555555 });

    // Test counter addressing with random data
    test!(let mut seed = 0;
          for i in (0..0x100000) { MEMORY[i] = prng32(&mut seed) });

    // Test random addressing with counter data
    test!(let mut seed = 0;
          for i in (0..0x10000) { MEMORY[prng16(&mut seed)] = i });

    *wrong == 0
}

fn startup() -> bool {
    if check_integrity() {
        println!("Bootloader CRC passed");
    } else {
        println!("Bootloader CRC failed");
        return false
    }

    println!("Gateware ident {}", board::ident::read(&mut [0; 64]));

    println!("Initializing SDRAM...");

    if unsafe { board::sdram::init(Some(&mut Console)) } {
        println!("SDRAM initialized");
    } else {
        println!("SDRAM initialization failed");
        return false
    }

    let (mut total, mut wrong) = (0, 0);
    if memory_test(&mut total, &mut wrong) {
        println!("Memory test passed");
    } else {
        println!("Memory test failed ({}/{} words incorrect)", wrong, total);
        return false
    }

    true
}

fn flash_boot() {
    const FIRMWARE: *mut u8 = board::mem::FLASH_BOOT_ADDRESS as *mut u8;
    const MAIN_RAM: *mut u8 = board::mem::MAIN_RAM_BASE as *mut u8;

    println!("Booting from flash...");

    let header = unsafe { slice::from_raw_parts(FIRMWARE, 8) };
    let length = BigEndian::read_u32(&header[0..]) as usize;
    let expected_crc = BigEndian::read_u32(&header[4..]);

    if length == 0xffffffff {
        println!("No firmware present");
        return
    } else if length > 4 * 1024 * 1024 {
        println!("Firmware too large (is it corrupted?)");
        return
    }

    let firmware_in_flash = unsafe { slice::from_raw_parts(FIRMWARE.offset(8), length) };
    let actual_crc = crc32::checksum_ieee(firmware_in_flash);

    if actual_crc == expected_crc {
        let firmware_in_sdram = unsafe { slice::from_raw_parts_mut(MAIN_RAM, length) };
        firmware_in_sdram.copy_from_slice(firmware_in_flash);

        println!("Starting firmware.");
        unsafe { boot::jump(MAIN_RAM as usize) }
    } else {
        println!("Firmware CRC failed (actual {:08x}, expected {:08x})",
                 actual_crc, expected_crc);
    }
}

#[cfg(has_ethmac)]
fn network_boot() {
    use smoltcp::wire::{EthernetAddress, IpAddress, IpCidr};

    println!("Initializing network...");

    let eth_addr = match config::read_str("mac", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => addr,
        _ => EthernetAddress([0x02, 0x00, 0x00, 0x00, 0x00, 0x01])
    };

    let ip_addr = match config::read_str("ip", |r| r.map(|s| s.parse())) {
        Ok(Ok(addr)) => addr,
        _ => IpAddress::v4(192, 168, 1, 50)
    };

    println!("Using MAC address {} and IP address {}", eth_addr, ip_addr);

    let mut net_device = unsafe { ethmac::EthernetDevice::new() };
    net_device.reset_phy_if_any();

    let mut neighbor_map = [None; 2];
    let neighbor_cache =
        smoltcp::iface::NeighborCache::new(&mut neighbor_map[..]);
    let mut ip_addrs = [IpCidr::new(ip_addr, 0)];
    let mut interface  =
        smoltcp::iface::EthernetInterfaceBuilder::new(net_device)
                       .neighbor_cache(neighbor_cache)
                       .ethernet_addr(eth_addr)
                       .ip_addrs(&mut ip_addrs[..])
                       .finalize();

    let mut socket_set_storage = [];
    let mut sockets =
        smoltcp::socket::SocketSet::new(&mut socket_set_storage[..]);

    println!("Waiting for connections...");

    loop {
        match interface.poll(&mut sockets, clock::get_ms()) {
            Ok(_) => (),
            Err(smoltcp::Error::Unrecognized) => (),
            Err(err) => println!("Network error: {}", err)
        }
    }
}

#[no_mangle]
pub extern fn main() -> i32 {
    println!("");
    println!(r" __  __ _ ____         ____ ");
    println!(r"|  \/  (_) ___|  ___  / ___|");
    println!(r"| |\/| | \___ \ / _ \| |    ");
    println!(r"| |  | | |___) | (_) | |___ ");
    println!(r"|_|  |_|_|____/ \___/ \____|");
    println!("");
    println!("MiSoC Bootloader");
    println!("Copyright (c) 2017-2018 M-Labs Limited");
    println!("");

    if startup() {
        println!("");
        flash_boot();
        #[cfg(has_ethmac)]
        network_boot();
    } else {
        println!("Halting.");
    }

    loop {}
}

#[no_mangle]
pub extern fn exception(vect: u32, _regs: *const u32, pc: u32, ea: u32) {
    panic!("exception {} at PC {:#08x}, EA {:#08x}", vect, pc, ea)
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
