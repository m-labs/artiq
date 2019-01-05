use core::{str, fmt};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    AlreadyLocked,
    SpaceExhausted,
    Truncated { offset: usize },
    InvalidSize { offset: usize, size: usize },
    MissingSeparator { offset: usize },
    Utf8Error(str::Utf8Error),
    NoFlash,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            &Error::AlreadyLocked =>
                write!(f, "attempt at reentrant access"),
            &Error::SpaceExhausted =>
                write!(f, "space exhausted"),
            &Error::Truncated { offset }=>
                write!(f, "truncated record at offset {}", offset),
            &Error::InvalidSize { offset, size } =>
                write!(f, "invalid record size {} at offset {}", size, offset),
            &Error::MissingSeparator { offset } =>
                write!(f, "missing separator at offset {}", offset),
            &Error::Utf8Error(err) =>
                write!(f, "{}", err),
            &Error::NoFlash =>
                write!(f, "flash memory is not present"),
        }
    }
}

#[cfg(has_spiflash)]
mod imp {
    use core::str;
    use byteorder::{ByteOrder, BigEndian};
    use cache;
    use spiflash;
    use super::Error;
    use core::fmt;
    use core::fmt::Write;

    struct FmtWrapper<'a> {
        buf: &'a mut [u8],
        offset: usize,
    }

    impl<'a> FmtWrapper<'a> {
        fn new(buf: &'a mut [u8]) -> Self {
            FmtWrapper {
                buf: buf,
                offset: 0,
            }
        }

        fn contents(&self) -> &[u8] {
            &self.buf[..self.offset]
        }
    }

    impl<'a> fmt::Write for FmtWrapper<'a> {
        fn write_str(&mut self, s: &str) -> fmt::Result {
            let bytes = s.as_bytes();
            let remainder = &mut self.buf[self.offset..];
            let remainder = &mut remainder[..bytes.len()];
            remainder.copy_from_slice(bytes);
            self.offset += bytes.len();
            Ok(())
        }
    }

    // One flash sector immediately before the firmware.
    const ADDR: usize = ::mem::FLASH_BOOT_ADDRESS - spiflash::SECTOR_SIZE;
    const SIZE: usize = spiflash::SECTOR_SIZE;

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

            pub fn data(&self) -> &'static [u8] {
                unsafe { slice::from_raw_parts(super::ADDR as *const u8, super::SIZE) }
            }
        }

        impl Drop for Lock {
            fn drop(&mut self) {
                LOCKED.store(0, Ordering::SeqCst)
            }
        }
    }

    use self::lock::Lock;

    #[derive(Clone)]
    struct Iter<'a> {
        data:   &'a [u8],
        offset: usize
    }

    impl<'a> Iter<'a> {
        fn new(data: &'a [u8]) -> Iter<'a> {
            Iter { data: data, offset: 0 }
        }
    }

    impl<'a> Iterator for Iter<'a> {
        type Item = Result<(&'a [u8], &'a [u8]), Error>;

        fn next(&mut self) -> Option<Self::Item> {
            let data = &self.data[self.offset..];

            if data.len() < 4 {
                // error!("offset {}: truncated record", self.offset);
                return Some(Err(Error::Truncated { offset: self.offset }))
            }

            let record_size = BigEndian::read_u32(data) as usize;
            if record_size == !0 /* all ones; erased flash */ {
                return None
            } else if record_size < 4 || record_size > data.len() {
                return Some(Err(Error::InvalidSize { offset: self.offset, size: record_size }))
            }

            let record_body = &data[4..record_size];
            match record_body.iter().position(|&x| x == 0) {
                None => {
                    return Some(Err(Error::MissingSeparator { offset: self.offset }))
                }
                Some(pos) => {
                    self.offset += record_size;

                    let (key, zero_and_value) = record_body.split_at(pos);
                    Some(Ok((key, &zero_and_value[1..])))
                }
            }
        }
    }

    pub fn read<F: FnOnce(Result<&[u8], Error>) -> R, R>(key: &str, f: F) -> R {
        f(Lock::take().and_then(|lock| {
            let mut iter = Iter::new(lock.data());
            let mut value = &[][..];
            while let Some(result) = iter.next() {
                let (record_key, record_value) = result?;
                if key.as_bytes() == record_key {
                    // last write wins
                    value = record_value
                }
            }
            Ok(value)
        }))
    }

    pub fn read_str<F: FnOnce(Result<&str, Error>) -> R, R>(key: &str, f: F) -> R {
        read(key, |result| {
            f(result.and_then(|value| str::from_utf8(value).map_err(Error::Utf8Error)))
        })
    }

    unsafe fn append_at(data: &[u8], mut offset: usize,
                        key: &[u8], value: &[u8]) -> Result<usize, Error> {
        let record_size = 4 + key.len() + 1 + value.len();
        if offset + record_size > data.len() {
            return Err(Error::SpaceExhausted)
        }

        let mut record_size_bytes = [0u8; 4];
        BigEndian::write_u32(&mut record_size_bytes[..], record_size as u32);

        {
            let mut write = |payload| {
                spiflash::write(data.as_ptr().offset(offset as isize) as usize, payload);
                offset += payload.len();
            };

            write(&record_size_bytes[..]);
            write(key);
            write(&[0]);
            write(value);
            cache::flush_l2_cache();
        }

        Ok(offset)
    }

    fn compact() -> Result<(), Error> {
        let lock = Lock::take()?;
        let data = lock.data();

        static mut OLD_DATA: [u8; SIZE] = [0; SIZE];
        let old_data = unsafe {
            OLD_DATA.copy_from_slice(data);
            &OLD_DATA[..]
        };

        unsafe { spiflash::erase_sector(data.as_ptr() as usize) };

        // This is worst-case quadratic, but we're limited by a small SPI flash sector size,
        // so it does not really matter.
        let mut offset = 0;
        let mut iter = Iter::new(old_data);
        'iter: while let Some(result) = iter.next() {
            let (key, mut value) = result?;
            if value.is_empty() {
                // This is a removed entry, ignore it.
                continue
            }

            let mut next_iter = iter.clone();
            while let Some(next_result) = next_iter.next() {
                let (next_key, _) = next_result?;
                if key == next_key {
                    // There's another entry that overwrites this one, ignore this one.
                    continue 'iter
                }
            }
            offset = unsafe { append_at(data, offset, key, value)? };
        }

        Ok(())
    }

    fn append(key: &str, value: &[u8]) -> Result<(), Error> {
        let lock = Lock::take()?;
        let data = lock.data();

        let free_offset = {
            let mut iter = Iter::new(data);
            while let Some(result) = iter.next() {
                let _ = result?;
            }
            iter.offset
        };

        unsafe { append_at(data, free_offset, key.as_bytes(), value)? };

        Ok(())
    }

    pub fn write(key: &str, value: &[u8]) -> Result<(), Error> {
        match append(key, value) {
            Err(Error::SpaceExhausted) => {
                compact()?;
                append(key, value)
            }
            res => res
        }
    }

    pub fn write_int(key: &str, value: u32) -> Result<(), Error> {
        let mut buf = [0; 16];
        let mut wrapper = FmtWrapper::new(&mut buf);
        write!(&mut wrapper, "{}", value).unwrap();
        write(key, wrapper.contents())
    }

    pub fn remove(key: &str) -> Result<(), Error> {
        write(key, &[])
    }

    pub fn erase() -> Result<(), Error> {
        let lock = Lock::take()?;
        let data = lock.data();

        unsafe { spiflash::erase_sector(data.as_ptr() as usize) };
        cache::flush_l2_cache();

        Ok(())
    }
}

#[cfg(not(has_spiflash))]
mod imp {
    use super::Error;

    pub fn read<F: FnOnce(Result<&[u8], Error>) -> R, R>(_key: &str, f: F) -> R {
        f(Err(Error::NoFlash))
    }

    pub fn read_str<F: FnOnce(Result<&str, Error>) -> R, R>(_key: &str, f: F) -> R {
        f(Err(Error::NoFlash))
    }

    pub fn write(_key: &str, _value: &[u8]) -> Result<(), Error> {
        Err(Error::NoFlash)
    }

    pub fn remove(_key: &str) -> Result<(), Error> {
        Err(Error::NoFlash)
    }

    pub fn erase() -> Result<(), Error> {
        Err(Error::NoFlash)
    }
}

pub use self::imp::*;
