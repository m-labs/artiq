use core::str;
use std::btree_map::BTreeMap;
use byteorder::{ByteOrder, BigEndian};
use board::{mem, csr, cache, spiflash};

const ADDR: usize = mem::FLASH_BOOT_ADDRESS + 0x80000 /* max runtime size */;
const SIZE: usize = csr::CONFIG_SPIFLASH_SECTOR_SIZE as usize;

mod lock {
    use core::slice;
    use core::sync::atomic::{AtomicUsize, Ordering};

    static LOCKED: AtomicUsize = AtomicUsize::new(0);

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

pub use self::lock::Lock;

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
        if record_size < 4 {
            error!("offset {}: invalid record size", self.offset);
            return Some(Err(()))
        }
        if record_size == !0 /* all ones; erased flash */ {
            return None
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

fn append_at(mut offset: usize, key: &[u8], value: &[u8]) -> Result<usize, ()> {
    let record_size = 4 + key.len() + 1 + value.len();
    if offset + record_size > SIZE {
        return Err(())
    }

    let mut record_size_bytes = [0u8; 4];
    BigEndian::write_u32(&mut record_size_bytes[..], record_size as u32);

    spiflash::write(ADDR + offset, &record_size_bytes[..]);
    offset += record_size_bytes.len();

    spiflash::write(ADDR + offset, key);
    offset += key.len();

    spiflash::write(ADDR + offset, &[0]);
    offset += 1;

    spiflash::write(ADDR + offset, value);
    offset += value.len();

    cache::flush_l2_cache();
    Ok(offset)
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

    spiflash::erase_sector(ADDR);
    cache::flush_l2_cache();

    let mut offset = 0;
    for (key, value) in items {
        offset = append_at(offset, key, value)?;
    }
    Ok(())
}

fn append(key: &str, value: &[u8]) -> Result<(), ()> {
    let lock = Lock::take()?;

    let free_offset = {
        let mut iter = Iter::new(lock.data());
        while let Some(result) = iter.next() {
            let _ = result?;
        }
        iter.offset
    };

    append_at(free_offset, key.as_bytes(), value)?;
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
    let _lock = Lock::take()?;

    spiflash::erase_sector(ADDR);
    cache::flush_l2_cache();

    Ok(())
}
