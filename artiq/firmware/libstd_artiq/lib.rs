#![feature(lang_items, asm, alloc, collections, needs_panic_runtime,
           unicode, raw, int_error_internals, try_from, macro_reexport,
           allow_internal_unstable, stmt_expr_attributes, str_internals)]
#![no_std]
#![needs_panic_runtime]

extern crate std_unicode;
extern crate alloc;
#[macro_use]
#[macro_reexport(vec, format)]
extern crate collections;

pub use core::{any, cell, clone, cmp, convert, default, hash, iter, marker, mem, num,
    ops, option, ptr, result, sync,
    char, i16, i32, i64, i8, isize, u16, u32, u64, u8, usize, f32, f64};
pub use alloc::{arc, rc, oom, raw_vec};
pub use collections::{binary_heap, borrow, boxed, btree_map, btree_set, fmt, linked_list, slice,
    str, string, vec, vec_deque};

pub mod prelude {
    pub mod v1 {
        pub use core::prelude::v1::*;
        pub use collections::boxed::Box;
        pub use collections::borrow::ToOwned;
        pub use collections::string::{String, ToString};
        pub use collections::vec::Vec;
    }
}

pub mod error;
pub mod io;

// Provide Box::new wrapper
#[cfg(any(not(feature="alloc"), not(feature="io_error_alloc")))]
struct FakeBox<T>(core::marker::PhantomData<T>);
#[cfg(any(not(feature="alloc"), not(feature="io_error_alloc")))]
impl<T> FakeBox<T> {
    fn new(val: T) -> T {
        val
    }
}
