#![feature(alloc, allocator_api)]
#![no_std]

extern crate alloc;

use core::{mem, fmt};
use alloc::allocator::{Layout, AllocErr, Alloc};

// The minimum alignment guaranteed by the architecture.
const MIN_ALIGN: usize = 4;

const MAGIC_FREE: usize = 0xDEADDEAD;
const MAGIC_BUSY: usize = 0xFEEDFEED;

#[derive(Debug)]
struct Header {
    magic: usize,
    size:  usize,
    next:  *mut Header
}

pub struct ListAlloc {
    root:  *mut Header
}

pub const EMPTY: ListAlloc = ListAlloc { root: 0 as *mut Header };

impl ListAlloc {
    pub unsafe fn add(&mut self, ptr: *mut u8, size: usize) {
        let header_size = mem::size_of::<Header>();
        if size < header_size * 2 { return }

        let curr = ptr as *mut Header;
        (*curr).magic = MAGIC_FREE;
        (*curr).size  = size - header_size;
        (*curr).next  = self.root;
        self.root = curr;
    }

    pub unsafe fn add_range(&mut self, begin: *mut u8, end: *mut u8) {
        self.add(begin, end as usize - begin as usize)
    }
}

unsafe impl<'a> Alloc for &'a ListAlloc {
    unsafe fn alloc(&mut self, layout: Layout) -> Result<*mut u8, AllocErr> {
        if layout.align() > MIN_ALIGN {
            return Err(AllocErr::Unsupported { details: "alignment too large" })
        }

        let header_size = mem::size_of::<Header>();
        let size;
        if layout.size() % header_size != 0 {
            size = layout.size() + header_size - (layout.size() % header_size);
        } else {
            size = layout.size()
        }

        let mut curr = self.root;
        while !curr.is_null() {
            match (*curr).magic {
                MAGIC_BUSY => (),
                MAGIC_FREE => {
                    let mut next = (*curr).next;
                    while !next.is_null() && (*next).magic == MAGIC_FREE {
                        // Join
                        (*next).magic = 0;
                        (*curr).size += (*next).size + header_size;
                        (*curr).next  = (*next).next;
                        next = (*curr).next;
                    }

                    if (*curr).size > size + header_size * 2 {
                        // Split
                        let offset = header_size + size;
                        let next = (curr as *mut u8).offset(offset as isize) as *mut Header;
                        (*next).magic = MAGIC_FREE;
                        (*next).size  = (*curr).size - offset;
                        (*next).next  = (*curr).next;
                        (*curr).next  = next;
                        (*curr).size  = size;
                    }

                    if (*curr).size >= size {
                        (*curr).magic = MAGIC_BUSY;
                        return Ok(curr.offset(1) as *mut u8)
                    }
                },
                _ => panic!("heap corruption detected at {:p}", curr)
            }

            curr = (*curr).next;
        }

        Err(AllocErr::Exhausted { request: layout })
    }

    unsafe fn dealloc(&mut self, ptr: *mut u8, _layout: Layout) {
        let curr = (ptr as *mut Header).offset(-1);
        if (*curr).magic != MAGIC_BUSY {
            panic!("heap corruption detected at {:p}", curr)
        }
        (*curr).magic = MAGIC_FREE;
    }

    fn oom(&mut self, err: AllocErr) -> ! {
        panic!("heap view: {}\ncannot allocate: {:?}", self, err)
    }
}

impl fmt::Display for ListAlloc {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        unsafe {
            let mut total_busy = 0;
            let mut total_idle = 0;
            let mut total_meta = 0;

            let mut curr = self.root;
            while !curr.is_null() {
                total_meta += mem::size_of::<Header>();

                let desc = match (*curr).magic {
                    MAGIC_FREE => { total_idle += (*curr).size; "IDLE" },
                    MAGIC_BUSY => { total_busy += (*curr).size; "BUSY" },
                    _ => "!!!!"
                };

                write!(f, "{} {:p} + {:#x} + {:#x} -> {:p}\n",
                       desc, curr, mem::size_of::<Header>(), (*curr).size, (*curr).next)?;
                match (*curr).magic {
                    MAGIC_FREE | MAGIC_BUSY => (),
                    _ => break
                }

                curr = (*curr).next;
            }

            write!(f, " === busy: {:#x} idle: {:#x} meta: {:#x} total: {:#x}\n",
                   total_busy, total_idle, total_meta,
                   total_busy + total_idle + total_meta)
        }
    }
}
