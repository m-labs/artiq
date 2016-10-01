use std::vec::Vec;
use std::string::String;
use std::btree_map::BTreeMap;

#[derive(Debug)]
struct Entry {
    data: Vec<u32>,
    borrowed: bool
}

#[derive(Debug)]
pub struct Cache {
    entries: BTreeMap<String, Entry>
}

impl Cache {
    pub fn new() -> Cache {
        Cache { entries: BTreeMap::new() }
    }

    pub fn get(&mut self, key: &str) -> *const [u32] {
        match self.entries.get_mut(key) {
            None => &[],
            Some(ref mut entry) => {
                entry.borrowed = true;
                &entry.data[..]
            }
        }
    }

    pub fn put(&mut self, key: &str, data: &[u32]) -> Result<(), ()> {
        match self.entries.get_mut(key) {
            None => (),
            Some(ref mut entry) => {
                if entry.borrowed { return Err(()) }
                entry.data = Vec::from(data);
                return Ok(())
            }
        }

        self.entries.insert(String::from(key), Entry {
            data: Vec::from(data),
            borrowed: false
        });
        Ok(())
    }
}
