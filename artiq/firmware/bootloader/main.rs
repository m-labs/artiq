#![no_std]
#![feature(panic_implementation, panic_info_message)]

extern crate crc;
extern crate byteorder;
extern crate smoltcp;
#[macro_use]
extern crate board_misoc;

use core::{ptr, slice};
use crc::crc32;
use byteorder::{ByteOrder, BigEndian};
use board_misoc::{ident, cache, sdram, config, boot, mem as board_mem};
#[cfg(has_slave_fpga_cfg)]
use board_misoc::slave_fpga;
#[cfg(has_ethmac)]
use board_misoc::{clock, ethmac, net_settings};
use board_misoc::uart_console::Console;

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
    const MEMORY: *mut u32 = board_mem::MAIN_RAM_BASE as *mut u32;

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

    for _ in 0..4 {
        // Test data bus
        test!((); for i in (0..0x100) { MEMORY[i] = 0xAAAAAAAA });
        test!((); for i in (0..0x100) { MEMORY[i] = 0x55555555 });

        // Test counter addressing with random data
        test!(let mut seed = 0;
            for i in (0..0x100000) { MEMORY[i] = prng32(&mut seed) });

        // Test random addressing with counter data
        test!(let mut seed = 0;
            for i in (0..0x10000) { MEMORY[prng16(&mut seed)] = i });
    }
    *wrong == 0
}

fn startup() -> bool {
    if check_integrity() {
        println!("Bootloader CRC passed");
    } else {
        println!("Bootloader CRC failed");
        return false
    }

    println!("Gateware ident {}", ident::read(&mut [0; 64]));

    println!("Initializing SDRAM...");

    if unsafe { sdram::init(Some(&mut Console)) } {
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

#[cfg(has_slave_fpga_cfg)]
fn load_slave_fpga() {
    println!("Loading slave FPGA gateware...");

    const GATEWARE: *mut u8 = board_misoc::csr::CONFIG_SLAVE_FPGA_GATEWARE as *mut u8;

    let header = unsafe { slice::from_raw_parts(GATEWARE, 8) };
    let magic = BigEndian::read_u32(&header[0..]);
    let length = BigEndian::read_u32(&header[4..]) as usize;
    println!("  magic: 0x{:08x}, length: 0x{:08x}", magic, length);
    if magic != 0x5352544d {
        println!("  ...Error: bad magic");
        return
    }
    if length > 0x220000 {
        println!("  ...Error: too long (corrupted?)");
        return
    }
    let payload = unsafe { slice::from_raw_parts(GATEWARE.offset(8), length) };

    if let Err(e) = slave_fpga::prepare() {
        println!("  ...Error during preparation: {}", e);
        return
    }
    if let Err(e) = slave_fpga::input(payload) {
        println!("  ...Error during loading: {}", e);
        return
    }
    if let Err(e) = slave_fpga::startup() {
        println!("  ...Error during startup: {}", e);
        return
    }

    println!("  ...done");
}

fn flash_boot() {
    const FIRMWARE: *mut u8 = board_mem::FLASH_BOOT_ADDRESS as *mut u8;
    const MAIN_RAM: *mut u8 = board_mem::MAIN_RAM_BASE as *mut u8;

    println!("Booting from flash...");

    let header = unsafe { slice::from_raw_parts(FIRMWARE, 8) };
    let length = BigEndian::read_u32(&header[0..]) as usize;
    let expected_crc = BigEndian::read_u32(&header[4..]);

    if length == 0 || length == 0xffffffff {
        println!("No firmware present");
        return
    } else if length > 4 * 1024 * 1024 {
        println!("Firmware too large (is it corrupted?)");
        return
    }

    let firmware_in_flash = unsafe { slice::from_raw_parts(FIRMWARE.offset(8), length) };
    let actual_crc_flash = crc32::checksum_ieee(firmware_in_flash);

    if actual_crc_flash == expected_crc {
        let firmware_in_sdram = unsafe { slice::from_raw_parts_mut(MAIN_RAM, length) };
        firmware_in_sdram.copy_from_slice(firmware_in_flash);

        let actual_crc_sdram = crc32::checksum_ieee(firmware_in_sdram);
        if actual_crc_sdram == expected_crc {
            println!("Starting firmware.");
            unsafe { boot::jump(MAIN_RAM as usize) }
        } else {
            println!("Firmware CRC failed in SDRAM (actual {:08x}, expected {:08x})",
                     actual_crc_sdram, expected_crc);
        }
    } else {
        println!("Firmware CRC failed in flash (actual {:08x}, expected {:08x})",
                 actual_crc_flash, expected_crc);
    }
}

#[cfg(has_ethmac)]
enum NetConnState {
    WaitCommand,
    FirmwareLength(usize, u8),
    FirmwareDownload(usize, usize),
    FirmwareWaitO,
    FirmwareWaitK,
    #[cfg(has_slave_fpga_cfg)]
    GatewareLength(usize, u8),
    #[cfg(has_slave_fpga_cfg)]
    GatewareDownload(usize, usize),
    #[cfg(has_slave_fpga_cfg)]
    GatewareWaitO,
    #[cfg(has_slave_fpga_cfg)]
    GatewareWaitK
}

#[cfg(has_ethmac)]
struct NetConn {
    state: NetConnState,
    firmware_downloaded: bool
}

#[cfg(has_ethmac)]
impl NetConn {
    pub fn new() -> NetConn {
        NetConn {
            state: NetConnState::WaitCommand,
            firmware_downloaded: false
        }
    }

    pub fn reset(&mut self) {
        self.state = NetConnState::WaitCommand;
        self.firmware_downloaded = false;
    }

    // buf must contain at least one byte
    // this function must consume at least one byte
    fn input_partial(&mut self, buf: &[u8], mut boot_callback: impl FnMut()) -> Result<usize, ()> {
        match self.state {
            NetConnState::WaitCommand => {
                match buf[0] {
                    b'F' => {
                        println!("Received firmware load command");
                        self.state = NetConnState::FirmwareLength(0, 0);
                        Ok(1)
                    },
                    #[cfg(has_slave_fpga_cfg)]
                    b'G' => {
                        println!("Received gateware load command");
                        self.state = NetConnState::GatewareLength(0, 0);
                        Ok(1)
                    }
                    b'B' => {
                        if self.firmware_downloaded {
                            println!("Received boot command");
                            boot_callback();
                            self.state = NetConnState::WaitCommand;
                            Ok(1)
                        } else {
                            println!("Received boot command, but no firmware downloaded");
                            Err(())
                        }
                    },
                    _ => {
                        println!("Received unknown netboot command: 0x{:02x}", buf[0]);
                        Err(())
                    }
                }
            },

            NetConnState::FirmwareLength(firmware_length, recv_bytes) => {
                let firmware_length = (firmware_length << 8) | (buf[0] as usize);
                let recv_bytes = recv_bytes + 1;
                if recv_bytes == 4 {
                    self.state = NetConnState::FirmwareDownload(firmware_length, 0);
                } else {
                    self.state = NetConnState::FirmwareLength(firmware_length, recv_bytes);
                }
                Ok(1)
            },
            NetConnState::FirmwareDownload(firmware_length, recv_bytes) => {
                let max_length = firmware_length - recv_bytes;
                let buf = if buf.len() > max_length {
                    &buf[..max_length]
                } else {
                    &buf[..]
                };
                let length = buf.len();

                let firmware_in_sdram = unsafe { slice::from_raw_parts_mut((board_mem::MAIN_RAM_BASE + recv_bytes) as *mut u8, length) };
                firmware_in_sdram.copy_from_slice(buf);

                let recv_bytes = recv_bytes + length;
                if recv_bytes == firmware_length {
                    self.state = NetConnState::FirmwareWaitO;
                    Ok(length)
                } else {
                    self.state = NetConnState::FirmwareDownload(firmware_length, recv_bytes);
                    Ok(length)
                }
            },
            NetConnState::FirmwareWaitO => {
                if buf[0] == b'O' {
                    self.state = NetConnState::FirmwareWaitK;
                    Ok(1)
                } else {
                    println!("End-of-firmware confirmation failed");
                    Err(())
                }
            },
            NetConnState::FirmwareWaitK => {
                if buf[0] == b'K' {
                    println!("Firmware successfully downloaded");
                    self.state = NetConnState::WaitCommand;
                    self.firmware_downloaded = true;
                    Ok(1)
                } else {
                    println!("End-of-firmware confirmation failed");
                    Err(())
                }
            }

            #[cfg(has_slave_fpga_cfg)]
            NetConnState::GatewareLength(gateware_length, recv_bytes) => {
                let gateware_length = (gateware_length << 8) | (buf[0] as usize);
                let recv_bytes = recv_bytes + 1;
                if recv_bytes == 4 {
                    if let Err(e) = slave_fpga::prepare() {
                        println!(" Error during slave FPGA preparation: {}", e);
                        return Err(())
                    }
                    self.state = NetConnState::GatewareDownload(gateware_length, 0);
                } else {
                    self.state = NetConnState::GatewareLength(gateware_length, recv_bytes);
                }
                Ok(1)
            },
            #[cfg(has_slave_fpga_cfg)]
            NetConnState::GatewareDownload(gateware_length, recv_bytes) => {
                let max_length = gateware_length - recv_bytes;
                let buf = if buf.len() > max_length {
                    &buf[..max_length]
                } else {
                    &buf[..]
                };
                let length = buf.len();

                if let Err(e) = slave_fpga::input(buf) {
                    println!("Error during slave FPGA loading: {}", e);
                    return Err(())
                }

                let recv_bytes = recv_bytes + length;
                if recv_bytes == gateware_length {
                    self.state = NetConnState::GatewareWaitO;
                    Ok(length)
                } else {
                    self.state = NetConnState::GatewareDownload(gateware_length, recv_bytes);
                    Ok(length)
                }
            },
            #[cfg(has_slave_fpga_cfg)]
            NetConnState::GatewareWaitO => {
                if buf[0] == b'O' {
                    self.state = NetConnState::GatewareWaitK;
                    Ok(1)
                } else {
                    println!("End-of-gateware confirmation failed");
                    Err(())
                }
            },
            #[cfg(has_slave_fpga_cfg)]
            NetConnState::GatewareWaitK => {
                if buf[0] == b'K' {
                    if let Err(e) = slave_fpga::startup() {
                        println!("Error during slave FPGA startup: {}", e);
                        return Err(())
                    }
                    println!("Gateware successfully downloaded");
                    self.state = NetConnState::WaitCommand;
                    Ok(1)
                } else {
                    println!("End-of-gateware confirmation failed");
                    Err(())
                }
            }
        }
    }

    fn input(&mut self, buf: &[u8], mut boot_callback: impl FnMut()) -> Result<(), ()> {
        let mut remaining = &buf[..];
        while !remaining.is_empty() {
            let read_cnt = self.input_partial(remaining, &mut boot_callback)?;
            remaining = &remaining[read_cnt..];
        }
        Ok(())
    }
}

#[cfg(has_ethmac)]
fn network_boot() {
    use smoltcp::wire::IpCidr;

    println!("Initializing network...");

    let mut net_device = unsafe { ethmac::EthernetDevice::new() };
    net_device.reset_phy_if_any();

    let mut neighbor_map = [None; 2];
    let neighbor_cache =
        smoltcp::iface::NeighborCache::new(&mut neighbor_map[..]);
    let net_addresses = net_settings::get_adresses();
    println!("Network addresses: {}", net_addresses);
    let mut ip_addrs = [
        IpCidr::new(net_addresses.ipv4_addr, 0),
        IpCidr::new(net_addresses.ipv6_ll_addr, 0),
        IpCidr::new(net_addresses.ipv6_ll_addr, 0)
    ];
    let mut interface = match net_addresses.ipv6_addr {
        Some(addr) => {
            ip_addrs[2] = IpCidr::new(addr, 0);
            smoltcp::iface::EthernetInterfaceBuilder::new(net_device)
                       .ethernet_addr(net_addresses.hardware_addr)
                       .ip_addrs(&mut ip_addrs[..])
                       .neighbor_cache(neighbor_cache)
                       .finalize()
        }
        None =>
            smoltcp::iface::EthernetInterfaceBuilder::new(net_device)
                       .ethernet_addr(net_addresses.hardware_addr)
                       .ip_addrs(&mut ip_addrs[..2])
                       .neighbor_cache(neighbor_cache)
                       .finalize()
    };

    let mut rx_storage = [0; 4096];
    let mut tx_storage = [0; 128];

    let mut socket_set_entries: [_; 1] = Default::default();
    let mut sockets =
        smoltcp::socket::SocketSet::new(&mut socket_set_entries[..]);

    let tcp_rx_buffer = smoltcp::socket::TcpSocketBuffer::new(&mut rx_storage[..]);
    let tcp_tx_buffer = smoltcp::socket::TcpSocketBuffer::new(&mut tx_storage[..]);
    let tcp_socket = smoltcp::socket::TcpSocket::new(tcp_rx_buffer, tcp_tx_buffer);
    let tcp_handle = sockets.add(tcp_socket);

    let mut net_conn = NetConn::new();
    let mut boot_time = None;

    println!("Waiting for connections...");

    loop {
        let timestamp = clock::get_ms() as i64;
        {
            let socket = &mut *sockets.get::<smoltcp::socket::TcpSocket>(tcp_handle);

            match boot_time {
                None => {
                    if !socket.is_open() {
                        socket.listen(4269).unwrap() // 0x10ad
                    }

                    if socket.may_recv() {
                        if socket.recv(|data| {
                                    (data.len(), net_conn.input(data, || { boot_time = Some(timestamp + 20); }).is_err())
                                }).unwrap() {
                            net_conn.reset();
                            socket.close();
                        }
                    } else if socket.may_send() {
                        net_conn.reset();
                        socket.close();
                    }
                },
                Some(boot_time) => {
                    if timestamp > boot_time {
                        println!("Starting firmware.");
                        unsafe { boot::jump(board_mem::MAIN_RAM_BASE) }
                    }
                }
            }
        }

        match interface.poll(&mut sockets, smoltcp::time::Instant::from_millis(timestamp)) {
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
    println!("Copyright (c) 2017-2020 M-Labs Limited");
    println!("");

    #[cfg(has_ethmac)]
    clock::init();

    if startup() {
        println!("");
        if !config::read_str("no_flash_boot", |r| r == Ok("1")) {
            #[cfg(has_slave_fpga_cfg)]
            load_slave_fpga();
            flash_boot();
        } else {
            println!("Flash booting has been disabled.");
        }
        #[cfg(has_ethmac)]
        network_boot();
    } else {
        println!("Halting.");
    }

    println!("No boot medium.");
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
