use alloc::{vec::Vec, string::String, collections::btree_map::BTreeMap};
use cslice::{CSlice, AsCSlice};
use core::mem::transmute;

struct Entry {
    data: Vec<i32>,
    slice: CSlice<'static, i32>,
    borrowed: bool
}

impl core::fmt::Debug for Entry {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("Entry")
         .field("data", &self.data)
         .field("borrowed", &self.borrowed)
         .finish()
    }
}

pub struct Cache {
    entries: BTreeMap<String, Entry>,
    empty: CSlice<'static, i32>,
}

impl core::fmt::Debug for Cache {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("Cache")
         .field("entries", &self.entries)
         .finish()
    }
}

impl Cache {
    pub fn new() -> Cache {
        let empty_vec = vec![];
        let empty = unsafe {
            transmute::<CSlice<'_, i32>, CSlice<'static, i32>>(empty_vec.as_c_slice())
        };
        Cache { entries: BTreeMap::new(), empty }
    }

    pub fn get(&mut self, key: &str) -> *const CSlice<'static, i32> {
        match self.entries.get_mut(key) {
            None => &self.empty,
            Some(ref mut entry) => {
                entry.borrowed = true;
                &entry.slice
            }
        }
    }

    pub fn put(&mut self, key: &str, data: &[i32]) -> Result<(), ()> {
        match self.entries.get_mut(key) {
            None => (),
            Some(ref mut entry) => {
                if entry.borrowed { return Err(()) }
                entry.data = Vec::from(data);
                unsafe {
                    entry.slice = transmute::<CSlice<'_, i32>, CSlice<'static, i32>>(
                        entry.data.as_c_slice());
                }
                return Ok(())
            }
        }

        let data = Vec::from(data);
        let slice = unsafe {
            transmute::<CSlice<'_, i32>, CSlice<'static, i32>>(data.as_c_slice())
        };
        self.entries.insert(String::from(key), Entry {
            data,
            slice,
            borrowed: false
        });
        Ok(())
    }

    pub unsafe fn unborrow(&mut self) {
        for (_key, entry) in self.entries.iter_mut() {
            entry.borrowed = false;
        }
    }
}
