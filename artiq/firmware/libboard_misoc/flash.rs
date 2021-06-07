extern crate crc;
use core::fmt;


#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    AlreadyLocked,
    NoFlash,
    WrongPartition,
    WriteFail { sector: usize },
    CorruptedFirmware,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            &Error::AlreadyLocked =>
                write!(f, "attempt at reentrant access"),
            &Error::NoFlash =>
                write!(f, "flash memory is not present"),
            &Error::WrongPartition =>
                write!(f, "Unknown partition"),
            &Error::WriteFail { sector } =>
                write!(f, "Flash writing failed in sector {}", sector),
            &Error::CorruptedFirmware =>
                write!(f, "Corrupted file"),
        }
    }
}

#[cfg(has_spiflash)]
mod imp {
    use core::str;
    use cache;
    use spiflash;
    use super::Error;

    use core::slice;
    use core::cmp;
    use csr;
    use byteorder::{ByteOrder, BigEndian};
    use flash::crc::crc32;

    const SIZE: usize = spiflash::SECTOR_SIZE;
    const ADDR_GATEWARE: usize = 0x0;
    const ADDR_BOOTLOADER: usize = 0x400000;
    const ADDR_FIRMWARE: usize = ::mem::FLASH_BOOT_ADDRESS;

    mod lock {
        use core::slice;
        use core::sync::atomic::{AtomicUsize, Ordering, ATOMIC_USIZE_INIT};
        use super::Error;

        static LOCKED: AtomicUsize = ATOMIC_USIZE_INIT;

        pub struct Lock;

        impl Lock {
            pub fn take() -> Result<Lock, Error> {
                if LOCKED.swap(1, Ordering::SeqCst) != 0 {
                    Err(Error::AlreadyLocked)
                } else {
                    Ok(Lock)
                }
            }

            pub fn data(&self, addr: usize) -> &'static [u8] {
                unsafe { slice::from_raw_parts(addr as *const u8, super::SIZE) }
            }
        }
    }
    
    use self::lock::Lock;
    
    pub fn erase_sector(addr: usize) -> Result<(), Error> {
        let lock = Lock::take()?;
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
                println!("Firmware CRC failed (actual {:08x}, expected {:08x})", actual_crc, expected_crc);
                return Err(Error::CorruptedFirmware);
            }
            if expected_len != value.len() as u32 {
                println!("Firmware length failed (actual {:08x}, expected {:08x})", value.len(), expected_len);
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
        let firstsector: usize = addr / SIZE; 
        let lastsector: usize = (addr + value.len() - 1) / SIZE;
        println!("first sector is: {}, last sector is: {}", firstsector, lastsector);
        for offset in firstsector..lastsector+1 {
            let size = cmp::min(SIZE as usize, value.len());
            erase_sector(SIZE * offset);
            println!("Writing sector {}", offset);
            unsafe { spiflash::write(SIZE * offset as usize, &value[..size]) };
            cache::flush_l2_cache();
            // Verifying
            let get = unsafe { slice::from_raw_parts(
                    (SIZE * offset) as *const u8, SIZE) };
            for i in 0..size {
                if value[i as usize] != get[i as usize] {
                    println!("Error in byte No.{}, and the value is {:#02x}",
                    (offset - firstsector) * SIZE + i, get[i as usize]);
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

    pub fn reload () -> Result<(), Error> {

        unsafe {
            csr::icap::trigger_write(0);
            csr::icap::trigger_write(1);
        }

        Ok(())
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