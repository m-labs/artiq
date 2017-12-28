#[cfg(has_spiflash)]
mod imp {
    use core::str;
    use byteorder::{ByteOrder, BigEndian};
    use cache;
    use spiflash;

    // One flash sector immediately before the firmware.
    const ADDR: usize = ::mem::FLASH_BOOT_ADDRESS - spiflash::SECTOR_SIZE;
    const SIZE: usize = spiflash::SECTOR_SIZE;

    mod lock {
        use core::slice;
        use core::sync::atomic::{AtomicUsize, Ordering, ATOMIC_USIZE_INIT};

        static LOCKED: AtomicUsize = ATOMIC_USIZE_INIT;

        pub struct Lock;

        impl Lock {
            pub fn take() -> Result<Lock, ()> {
                if LOCKED.swap(1, Ordering::SeqCst) != 0 {
                    Err(()) // already locked
                } else {
                    Ok(Lock) // locked now
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
        type Item = Result<(&'a [u8], &'a [u8]), ()>;

        fn next(&mut self) -> Option<Self::Item> {
            let data = &self.data[self.offset..];

            if data.len() < 4 {
                error!("offset {}: truncated record", self.offset);
                return Some(Err(()))
            }

            let record_size = BigEndian::read_u32(data) as usize;
            if record_size == !0 /* all ones; erased flash */ {
                return None
            } else if record_size < 4 || record_size > data.len() {
                error!("offset {}: invalid record size {}", self.offset, record_size);
                return Some(Err(()))
            }

            let record_body = &data[4..record_size];
            match record_body.iter().position(|&x| x == 0) {
                None => {
                    error!("offset {}: missing separator", self.offset);
                    Some(Err(()))
                }
                Some(pos) => {
                    self.offset += record_size;

                    let (key, zero_and_value) = record_body.split_at(pos);
                    Some(Ok((key, &zero_and_value[1..])))
                }
            }
        }
    }

    pub fn read<F: FnOnce(Result<&[u8], ()>) -> R, R>(key: &str, f: F) -> R {
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

    pub fn read_str<F: FnOnce(Result<&str, ()>) -> R, R>(key: &str, f: F) -> R {
        read(key, |result| {
            f(result.and_then(|value| str::from_utf8(value).map_err(|_| ())))
        })
    }

    unsafe fn append_at<'a>(mut data: &'a [u8], key: &[u8], value: &[u8]) -> Result<&'a [u8], ()> {
        let record_size = 4 + key.len() + 1 + value.len();
        if data.len() < record_size {
            return Err(())
        }

        let mut record_size_bytes = [0u8; 4];
        BigEndian::write_u32(&mut record_size_bytes[..], record_size as u32);

        spiflash::write(data.as_ptr() as usize, &record_size_bytes[..]);
        data = &data[record_size_bytes.len()..];

        spiflash::write(data.as_ptr() as usize, key);
        data = &data[key.len()..];

        spiflash::write(data.as_ptr() as usize, &[0]);
        data = &data[1..];

        spiflash::write(data.as_ptr() as usize, value);
        data = &data[value.len()..];

        cache::flush_l2_cache();

        Ok(data)
    }

    fn compact() -> Result<(), ()> {
        let lock = Lock::take()?;

        static mut OLD_DATA: [u8; SIZE] = [0; SIZE];
        let old_data = unsafe {
            OLD_DATA.copy_from_slice(lock.data());
            &OLD_DATA[..]
        };

        let mut data = lock.data();
        unsafe { spiflash::erase_sector(data.as_ptr() as usize) };

        // This is worst-case quadratic, but we're limited by a small SPI flash sector size,
        // so it does not really matter.
        let mut iter = Iter::new(old_data);
        while let Some(result) = iter.next() {
            let (key, mut value) = result?;

            let mut next_iter = iter.clone();
            while let Some(next_result) = next_iter.next() {
                let (next_key, next_value) = next_result?;
                if key == next_key {
                    value = next_value
                }
            }
            data = unsafe { append_at(data, key, value)? };
        }

        Ok(())
    }

    fn append(key: &str, value: &[u8]) -> Result<(), ()> {
        let lock = Lock::take()?;

        let free = {
            let mut iter = Iter::new(lock.data());
            while let Some(result) = iter.next() {
                let _ = result?;
            }
            &iter.data[iter.offset..]
        };

        unsafe { append_at(free, key.as_bytes(), value)? };

        Ok(())
    }

    pub fn write(key: &str, value: &[u8]) -> Result<(), ()> {
        match append(key, value) {
            Ok(()) => (),
            Err(()) => {
                compact()?;
                append(key, value)?;
            }
        }
        Ok(())
    }

    pub fn remove(key: &str) -> Result<(), ()> {
        write(key, &[])
    }

    pub fn erase() -> Result<(), ()> {
        let lock = Lock::take()?;

        unsafe { spiflash::erase_sector(lock.data().as_ptr() as usize) };
        cache::flush_l2_cache();

        Ok(())
    }
}

#[cfg(not(has_spiflash))]
mod imp {
    pub fn read<F: FnOnce(Result<&[u8], ()>) -> R, R>(_key: &str, f: F) -> R {
        f(Err(()))
    }

    pub fn read_str<F: FnOnce(Result<&str, ()>) -> R, R>(_key: &str, f: F) -> R {
        f(Err(()))
    }

    pub fn write(_key: &str, _value: &[u8]) -> Result<(), ()> {
        Err(())
    }

    pub fn remove(_key: &str) -> Result<(), ()> {
        Err(())
    }

    pub fn erase() -> Result<(), ()> {
        Err(())
    }
}

pub use self::imp::*;
