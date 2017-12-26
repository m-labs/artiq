#[cfg(has_spiflash)]
mod imp {
    use core::str;
    use std::btree_map::BTreeMap;
    use byteorder::{ByteOrder, BigEndian};
    use board::{cache, spiflash};

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
                extern {
                    static _fstorage: u8;
                    static _estorage: u8;
                }

                unsafe {
                    let begin = &_fstorage as *const u8;
                    let end   = &_estorage as *const u8;
                    slice::from_raw_parts(begin, end as usize - begin as usize)
                }
            }
        }

        impl Drop for Lock {
            fn drop(&mut self) {
                LOCKED.store(0, Ordering::SeqCst)
            }
        }
    }

    use self::lock::Lock;

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
                error!("offset {}: invalid record size", self.offset);
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

        Ok(data)
    }

    fn compact() -> Result<(), ()> {
        let lock = Lock::take()?;

        let mut items = BTreeMap::new();
        {
            let mut iter = Iter::new(lock.data());
            while let Some(result) = iter.next() {
                let (key, value) = result?;
                items.insert(key, value);
            }
        }

        let mut data = lock.data();
        spiflash::erase_sector(data.as_ptr() as usize);
        for (key, value) in items {
            data = unsafe { append_at(data, key, value)? };
        }

        cache::flush_l2_cache();
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

        cache::flush_l2_cache();
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

        spiflash::erase_sector(lock.data().as_ptr() as usize);
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
