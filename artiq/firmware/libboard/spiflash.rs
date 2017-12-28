use core::cmp;
use csr;

pub const SECTOR_SIZE: usize = csr::CONFIG_SPIFLASH_SECTOR_SIZE as usize;
pub const PAGE_SIZE:   usize = csr::CONFIG_SPIFLASH_PAGE_SIZE   as usize;

const PAGE_MASK: usize = PAGE_SIZE - 1;

const CMD_PP:   u8 = 0x02;
// const CMD_WRDI: u8 = 0x04;
const CMD_RDSR: u8 = 0x05;
const CMD_WREN: u8 = 0x06;
const CMD_SE:   u8 = 0xd8;

const PIN_CLK:  u8 = 1 << 1;
const PIN_CS_N: u8 = 1 << 2;
const PIN_DQ_I: u8 = 1 << 3;

const SR_WIP:   u8 = 1;

unsafe fn write_byte(mut byte: u8) {
    csr::spiflash::bitbang_write(0);
    for _ in 0..8 {
        csr::spiflash::bitbang_write((byte & 0x80) >> 7);
        csr::spiflash::bitbang_write((byte & 0x80) >> 7 | PIN_CLK);
        byte <<= 1;
    }
    csr::spiflash::bitbang_write(0);
}

unsafe fn write_addr(mut addr: usize) {
    csr::spiflash::bitbang_write(0);
    for _ in 0..24 {
        csr::spiflash::bitbang_write(((addr & 0x800000) >> 23) as u8);
        csr::spiflash::bitbang_write(((addr & 0x800000) >> 23) as u8 | PIN_CLK);
        addr <<= 1;
    }
    csr::spiflash::bitbang_write(0);
}

fn wait_until_ready() {
    unsafe {
        loop {
            let mut sr = 0;
            write_byte(CMD_RDSR);
            for _ in 0..8 {
                sr <<= 1;
                csr::spiflash::bitbang_write(PIN_DQ_I | PIN_CLK);
                sr |= csr::spiflash::miso_read();
                csr::spiflash::bitbang_write(PIN_DQ_I);
            }
            csr::spiflash::bitbang_write(0);
            csr::spiflash::bitbang_write(PIN_CS_N);
            if sr & SR_WIP == 0 {
                return
            }
        }
    }
}

pub unsafe fn erase_sector(addr: usize) {
    let sector_addr = addr & !(csr::CONFIG_SPIFLASH_SECTOR_SIZE as usize - 1);

    csr::spiflash::bitbang_en_write(1);

    wait_until_ready();

    write_byte(CMD_WREN);
    csr::spiflash::bitbang_write(PIN_CS_N);

    write_byte(CMD_SE);
    write_addr(sector_addr);
    csr::spiflash::bitbang_write(PIN_CS_N);

    wait_until_ready();

    csr::spiflash::bitbang_en_write(0);
}

unsafe fn write_page(addr: usize, data: &[u8]) {
    csr::spiflash::bitbang_en_write(1);

    wait_until_ready();

    write_byte(CMD_WREN);
    csr::spiflash::bitbang_write(PIN_CS_N);
    write_byte(CMD_PP);
    write_addr(addr);
    for &byte in data {
        write_byte(byte)
    }

    csr::spiflash::bitbang_write(PIN_CS_N);
    csr::spiflash::bitbang_write(0);

    wait_until_ready();

    csr::spiflash::bitbang_en_write(0);
}

pub unsafe fn write(mut addr: usize, mut data: &[u8]) {
    if addr & PAGE_MASK != 0 {
        let size = cmp::min((PAGE_SIZE - (addr & PAGE_MASK)) as usize, data.len());
        write_page(addr, &data[..size]);
        addr += size;
        data  = &data[size..];
    }

    while data.len() > 0 {
        let size = cmp::min(PAGE_SIZE as usize, data.len());
        write_page(addr, &data[..size]);
        addr += size;
        data  = &data[size..];
    }
}
