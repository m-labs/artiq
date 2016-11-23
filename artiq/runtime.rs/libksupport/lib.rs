#![feature(lang_items, needs_panic_runtime, asm, libc, stmt_expr_attributes)]

#![no_std]
#![needs_panic_runtime]

#[macro_use]
extern crate std_artiq as std;
extern crate libc;
extern crate byteorder;

#[path = "../src/board.rs"]
mod board;
#[path = "../src/mailbox.rs"]
mod mailbox;

#[path = "../src/proto.rs"]
mod proto;
#[path = "../src/kernel_proto.rs"]
mod kernel_proto;
#[path = "../src/rpc_proto.rs"]
mod rpc_proto;

mod dyld;
mod api;

#[allow(improper_ctypes)]
extern {
    fn __artiq_raise(exn: *const ::kernel_proto::Exception) -> !;
}

macro_rules! artiq_raise {
    ($name:expr, $message:expr, $param0:expr, $param1:expr, $param2:expr) => ({
        let exn = $crate::kernel_proto::Exception {
            name:     concat!("0:artiq.coredevice.exceptions.", $name, "\0").as_bytes().as_ptr(),
            file:     concat!(file!(), "\0").as_bytes().as_ptr(),
            line:     line!(),
            column:   column!(),
            // https://github.com/rust-lang/rfcs/pull/1719
            function: "(Rust function)\0".as_bytes().as_ptr(),
            message:  concat!($message, "\0").as_bytes().as_ptr(),
            param:    [$param0, $param1, $param2],
            phantom:  ::core::marker::PhantomData
        };
        #[allow(unused_unsafe)]
        unsafe { $crate::__artiq_raise(&exn as *const _) }
    });
    ($name:expr, $message:expr) => ({
        artiq_raise!($name, $message, 0, 0, 0)
    });
}

mod rtio;
#[cfg(has_i2c)]
mod i2c;

use core::{mem, ptr, slice, str};
use std::io::Cursor;
use libc::{c_char, size_t};
use kernel_proto::*;
use dyld::Library;

#[no_mangle]
pub extern "C" fn malloc(_size: usize) -> *mut libc::c_void {
    unimplemented!()
}

#[no_mangle]
pub extern "C" fn realloc(_ptr: *mut libc::c_void, _size: usize) -> *mut libc::c_void {
    unimplemented!()
}

#[no_mangle]
pub extern "C" fn free(_ptr: *mut libc::c_void) {
    unimplemented!()
}

fn send(request: &Message) {
    unsafe { mailbox::send(request as *const _ as usize) }
    while !mailbox::acknowledged() {}
}

fn recv<R, F: FnOnce(&Message) -> R>(f: F) -> R {
    while mailbox::receive() == 0 {}
    let result = f(unsafe { mem::transmute::<usize, &Message>(mailbox::receive()) });
    mailbox::acknowledge();
    result
}

macro_rules! recv {
    ($p:pat => $e:expr) => {
        recv(|request| {
            if let $p = request {
                $e
            } else {
                send(&Log(format_args!("unexpected reply: {:?}", request)));
                loop {}
            }
        })
    }
}

macro_rules! print {
    ($($arg:tt)*) => ($crate::send(&$crate::kernel_proto::Log(format_args!($($arg)*))));
}

macro_rules! println {
    ($fmt:expr) => (print!(concat!($fmt, "\n")));
    ($fmt:expr, $($arg:tt)*) => (print!(concat!($fmt, "\n"), $($arg)*));
}

#[path = "../src/rpc_queue.rs"]
mod rpc_queue;

#[lang = "panic_fmt"]
extern fn panic_fmt(args: core::fmt::Arguments, file: &'static str, line: u32) -> ! {
    println!("panic at {}:{}: {}", file, line, args);
    send(&RunAborted);
    loop {}
}

#[repr(C)]
pub struct ArtiqList<T> {
    len: usize,
    ptr: *const T
}

impl<T> ArtiqList<T> {
    pub fn from_slice(slice: &'static [T]) -> ArtiqList<T> {
        ArtiqList { ptr: slice.as_ptr(), len: slice.len() }
    }

    pub unsafe fn as_slice(&self) -> &[T] {
        slice::from_raw_parts(self.ptr, self.len)
    }
}

static mut NOW: u64 = 0;

#[no_mangle]
pub extern fn send_to_core_log(ptr: *const u8, len: usize) {
    send(&LogSlice(unsafe {
        str::from_utf8_unchecked(slice::from_raw_parts(ptr, len))
    }))
}

#[no_mangle]
pub extern fn send_to_rtio_log(timestamp: i64, ptr: *const u8, len: usize) {
    rtio::log(timestamp, unsafe { slice::from_raw_parts(ptr, len) })
}

extern fn abort() -> ! {
    println!("kernel called abort()");
    send(&RunAborted);
    loop {}
}

extern fn send_rpc(service: u32, tag: *const u8, data: *const *const ()) {
    extern { fn strlen(s: *const c_char) -> size_t; }
    let tag = unsafe { slice::from_raw_parts(tag, strlen(tag as *const c_char)) };

    while !rpc_queue::empty() {}
    send(&RpcSend {
        async:   false,
        service: service,
        tag:     tag,
        data:    data
    })
}

extern fn send_async_rpc(service: u32, tag: *const u8, data: *const *const ()) {
    extern { fn strlen(s: *const c_char) -> size_t; }
    let tag = unsafe { slice::from_raw_parts(tag, strlen(tag as *const c_char)) };

    while rpc_queue::full() {}
    rpc_queue::enqueue(|mut slice| {
        let length = {
            let mut writer = Cursor::new(&mut slice[4..]);
            try!(rpc_proto::send_args(&mut writer, service, tag, data));
            writer.position()
        };
        proto::write_u32(&mut slice, length as u32)
    }).unwrap_or_else(|err| {
        assert!(err.kind() == std::io::ErrorKind::WriteZero);

        while !rpc_queue::empty() {}
        send(&RpcSend {
            async:   true,
            service: service,
            tag:     tag,
            data:    data
        })
    })
}

extern fn recv_rpc(slot: *mut ()) -> usize {
    send(&RpcRecvRequest(slot));
    recv!(&RpcRecvReply(ref result) => {
        match result {
            &Ok(alloc_size) => alloc_size,
            &Err(ref exception) => unsafe { __artiq_raise(exception as *const _) }
        }
    })
}

#[no_mangle]
pub extern fn __artiq_terminate(exception: *const kernel_proto::Exception,
                            backtrace_data: *mut usize,
                            backtrace_size: usize) -> ! {
    let backtrace = unsafe { slice::from_raw_parts_mut(backtrace_data, backtrace_size) };
    let mut cursor = 0;
    for index in 0..backtrace.len() {
        if backtrace[index] > kernel_proto::KERNELCPU_PAYLOAD_ADDRESS {
            backtrace[cursor] = backtrace[index] - kernel_proto::KERNELCPU_PAYLOAD_ADDRESS;
            cursor += 1;
        }
    }
    let backtrace = &mut backtrace[0..cursor];

    send(&NowSave(unsafe { NOW }));
    send(&RunException {
        exception: unsafe { (*exception).clone() },
        backtrace: backtrace
    });
    loop {}
}

extern fn watchdog_set(ms: i64) -> i32 {
    if ms < 0 {
        artiq_raise!("ValueError", "cannot set a watchdog with a negative timeout")
    }

    send(&WatchdogSetRequest { ms: ms as u64 });
    recv!(&WatchdogSetReply { id } => id) as i32
}

extern fn watchdog_clear(id: i32) {
    send(&WatchdogClear { id: id as usize })
}

extern fn cache_get(key: *const u8) -> ArtiqList<i32> {
    extern { fn strlen(s: *const c_char) -> size_t; }
    let key = unsafe { slice::from_raw_parts(key, strlen(key as *const c_char)) };
    let key = unsafe { str::from_utf8_unchecked(key) };

    send(&CacheGetRequest { key: key });
    recv!(&CacheGetReply { value } => ArtiqList::from_slice(value))
}

extern fn cache_put(key: *const u8, list: ArtiqList<i32>) {
    extern { fn strlen(s: *const c_char) -> size_t; }
    let key = unsafe { slice::from_raw_parts(key, strlen(key as *const c_char)) };
    let key = unsafe { str::from_utf8_unchecked(key) };

    send(&CachePutRequest { key: key, value: unsafe { list.as_slice() } });
    recv!(&CachePutReply { succeeded } => {
        if !succeeded {
            artiq_raise!("CacheError", "cannot put into a busy cache row")
        }
    })
}

unsafe fn attribute_writeback(typeinfo: *const ()) {
    struct Attr {
        offset: usize,
        tag:    *const u8,
        name:   *const u8
    }

    struct Type {
        attributes: *const *const Attr,
        objects:    *const *const ()
    }

    let mut tys = typeinfo as *const *const Type;
    while !(*tys).is_null() {
        let ty = *tys;
        tys = tys.offset(1);

        let mut objects = (*ty).objects;
        while !(*objects).is_null() {
            let object = *objects;
            objects = objects.offset(1);

            let mut attributes = (*ty).attributes;
            while !(*attributes).is_null() {
                let attribute = *attributes;
                attributes = attributes.offset(1);

                if !(*attribute).tag.is_null() {
                    send_async_rpc(0, (*attribute).tag, [
                        &object as *const _ as *const (),
                        &(*attribute).name as *const _ as *const (),
                        (object as usize + (*attribute).offset) as *const ()
                    ].as_ptr());
                }
            }
        }
    }
}

#[no_mangle]
pub unsafe fn main() {
    let library = recv!(&LoadRequest(library) => {
        match Library::load(library, kernel_proto::KERNELCPU_PAYLOAD_ADDRESS, api::resolve) {
            Err(error) => {
                send(&LoadReply(Err(error)));
                loop {}
            },
            Ok(library) => {
                send(&LoadReply(Ok(())));
                library
            }
        }
    });

    let __bss_start = library.lookup("__bss_start");
    let _end = library.lookup("_end");
    ptr::write_bytes(__bss_start as *mut u8, 0, _end - __bss_start);

    send(&NowInitRequest);
    recv!(&NowInitReply(now) => NOW = now);
    (mem::transmute::<usize, fn()>(library.lookup("__modinit__")))();
    send(&NowSave(NOW));

    let typeinfo = library.lookup("typeinfo");
    if typeinfo != 0 {
        attribute_writeback(typeinfo as *const ())
    }

    send(&RunFinished);

    loop {}
}

#[no_mangle]
pub fn exception_handler(vect: u32, _regs: *const u32, pc: u32, ea: u32) {
    println!("exception {:?} at PC 0x{:x}, EA 0x{:x}", vect, pc, ea);
    send(&RunAborted)
}
