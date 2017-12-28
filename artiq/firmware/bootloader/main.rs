#![no_std]
#![feature(lang_items)]

extern crate rlibc;
extern crate crc;
#[macro_use]
extern crate board;

use core::slice;

fn check_integrity() -> bool {
    extern {
        static _begin: u8;
        static _end: u8;
        static _crc: u32;
    }

    unsafe {
        let length = &_end   as *const u8 as usize -
                     &_begin as *const u8 as usize;
        let bios = slice::from_raw_parts(&_begin as *const u8, length);
        crc::crc32::checksum_ieee(bios) == _crc
    }
}

fn initialize_sdram() -> bool {
    unsafe {
        board::sdram_phy::initialize();

        true
    }
}

#[no_mangle]
pub extern fn main() -> i32 {
    println!("");
    println!(r"    _    ____ _____ ___ ___  ");
    println!(r"   / \  |  _ \_   _|_ _/ _ \ ");
    println!(r"  / _ \ | |_) || |  | | | | |");
    println!(r" / ___ \|  _ < | |  | | |_| |");
    println!(r"/_/   \_\_| \_\|_| |___\__\_\");
    println!("");
    println!("ARTIQ Bootloader");
    println!("Copyright (c) 2017 M-Labs Limited");
    println!("Version {}", include_str!(concat!(env!("OUT_DIR"), "/git-describe")));
    println!("");

    if !check_integrity() {
        panic!("Bootloader CRC failed");
    } else {
        println!("Bootloader CRC passed");
    }

    if !initialize_sdram() {
        panic!("SDRAM initialization failed")
    } else {
        println!("SDRAM initialized");
    }

    loop {}
}

#[no_mangle]
pub extern fn exception(vect: u32, _regs: *const u32, pc: u32, ea: u32) {
    panic!("exception {} at PC {:#08x}, EA {:#08x}", vect, pc, ea)
}

#[no_mangle]
#[lang = "panic_fmt"]
pub extern fn panic_fmt(args: core::fmt::Arguments, file: &'static str, line: u32) -> ! {
    println!("panic at {}:{}: {}", file, line, args);
    loop {}
}
