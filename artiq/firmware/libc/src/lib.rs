// Helper crate for dealing with c ffi
#![allow(non_camel_case_types)]
#![no_std]
pub type c_char = i8;
pub type c_int = i32;
pub type size_t = usize;
pub type uintptr_t = usize;
pub type c_void = core::ffi::c_void;
