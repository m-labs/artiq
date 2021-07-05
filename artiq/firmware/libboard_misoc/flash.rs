extern crate crc;

#[cfg(has_spiflash)]
mod imp {
    use core::str;
    use cache;
    use spiflash;
    use spiflash::Error;

    use core::slice;
    use core::cmp;
    use csr;
    use byteorder::{ByteOrder, BigEndian};
    use flash::crc::crc32;

    const SIZE: usize = spiflash::SECTOR_SIZE;
    const ADDR_GATEWARE: usize = 0x0;
    const ADDR_BOOTLOADER: usize = 0x400000;
    const ADDR_FIRMWARE: usize = ::mem::FLASH_BOOT_ADDRESS;

    // use config::lock::Lock;
    use spiflash::lock::Lock;

    pub fn erase_sector(lock: &Lock, addr: usize) -> Result<(), Error> {
        let data = lock.data(addr);
        unsafe { spiflash::erase_sector(data.as_ptr() as usize) };
        cache::flush_l2_cache();
        Ok(())
    }
    
    pub fn write(key: &str, mut value: &[u8]) -> Result<(), Error> {
        if key == "firmware" {
            let expected_len = BigEndian::read_u32(&value[0..4]) + 8;
            let actual_crc = crc32::checksum_ieee(&value[8..]);
            let expected_crc = BigEndian::read_u32(&value[4..8]);
            if expected_crc != actual_crc {
                return Err(Error::CorruptedFirmware);
            }
            if expected_len != value.len() as u32 {
                return Err(Error::CorruptedFirmware);
            }
        }
        let mut addr: usize = 0x0;
        match key {
            "gateware" => { addr = ADDR_GATEWARE; }
            "bootloader" => { addr = ADDR_BOOTLOADER; }
            "firmware" => { addr = ADDR_FIRMWARE; }
            _ => { return Err(Error::WrongPartition); }
        }
        let mut lock = Lock::take()?;
        let firstsector: usize = addr / SIZE; 
        let lastsector: usize = (addr + value.len() - 1) / SIZE;
        for offset in firstsector..lastsector+1 {
            let size = cmp::min(SIZE as usize, value.len());
            erase_sector(&mut lock, SIZE * offset)?;
            unsafe { spiflash::write(SIZE * offset as usize, &value[..size]) };
            cache::flush_l2_cache();
            // Verifying
            let get = unsafe { slice::from_raw_parts (
                    (SIZE * offset) as *const u8, SIZE) };
            for i in 0..size {
                if value[i as usize] != get[i as usize] {
                    return Err(Error::WriteFail { sector: offset });
                }
            }
            value = &value[size..];
            if value.len() <= 0 {
                break;
            }
        }
        Ok(())
    }

    pub fn reload () -> ! {
        unsafe {
            csr::icap::iprog_write(1);
        }
        loop {}
    }
}

#[cfg(not(has_spiflash))]
mod imp {
    use super::Error;

    pub fn erase_sector(addr: usize) -> Result<(), Error> {
        f(Err(Error::NoFlash))
    }

    pub fn write(key: &str, mut value: &[u8]) -> Result<(), Error> {
        Err(Error::NoFlash)
    }

    pub fn reload () -> Result<(), Error> {
        Err(Error::NoFlash)
    }
}

pub use self::imp::*;
