use alloc::{Vec, String, BTreeMap};

#[derive(Debug)]
struct Entry {
    data: Vec<i32>,
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

    pub fn get(&mut self, key: &str) -> *const [i32] {
        match self.entries.get_mut(key) {
            None => &[],
            Some(ref mut entry) => {
                entry.borrowed = true;
                &entry.data[..]
            }
        }
    }

    pub fn put(&mut self, key: &str, data: &[i32]) -> Result<(), ()> {
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

    pub unsafe fn unborrow(&mut self) {
        for (_key, entry) in self.entries.iter_mut() {
            entry.borrowed = false;
        }
    }
}
