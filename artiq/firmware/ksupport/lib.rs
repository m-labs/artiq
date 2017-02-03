#![feature(lang_items, asm, libc)]
#![no_std]

extern crate alloc_none;
#[macro_use]
extern crate std_artiq as std;
extern crate libc;
extern crate byteorder;
extern crate board;
extern crate cslice;

#[path = "../runtime/mailbox.rs"]
mod mailbox;

#[path = "../runtime/proto.rs"]
mod proto;
#[path = "../runtime/kernel_proto.rs"]
mod kernel_proto;
#[path = "../runtime/rpc_proto.rs"]
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
            name:     concat!("0:artiq.coredevice.exceptions.", $name),
            file:     file!(),
            line:     line!(),
            column:   column!(),
            // https://github.com/rust-lang/rfcs/pull/1719
            function: "(Rust function)",
            message:  $message,
            param:    [$param0, $param1, $param2]
        };
        #[allow(unused_unsafe)]
        unsafe { $crate::__artiq_raise(&exn as *const _) }
    });
    ($name:expr, $message:expr) => ({
        artiq_raise!($name, $message, 0, 0, 0)
    });
}

use core::{mem, ptr, str};
use std::io::Cursor;
use cslice::{CSlice, CMutSlice, AsCSlice};
use kernel_proto::*;
use dyld::Library;

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

#[path = "../runtime/rpc_queue.rs"]
mod rpc_queue;
mod rtio;

#[no_mangle]
#[lang = "panic_fmt"]
pub extern fn panic_fmt(args: core::fmt::Arguments, file: &'static str, line: u32) -> ! {
    println!("panic at {}:{}: {}", file, line, args);
    send(&RunAborted);
    loop {}
}

static mut NOW: u64 = 0;

#[no_mangle]
pub extern fn send_to_core_log(text: CSlice<u8>) {
    match str::from_utf8(text.as_ref()) {
        Ok(s) => send(&LogSlice(s)),
        Err(e) => {
            send(&LogSlice(str::from_utf8(&text.as_ref()[..e.valid_up_to()]).unwrap()));
            send(&LogSlice("(invalid utf-8)\n"));
        }
    }
}

#[no_mangle]
pub extern fn send_to_rtio_log(timestamp: i64, text: CSlice<u8>) {
    rtio::log(timestamp, text.as_ref())
}

extern fn abort() -> ! {
    println!("kernel called abort()");
    send(&RunAborted);
    loop {}
}

extern fn send_rpc(service: u32, tag: CSlice<u8>, data: *const *const ()) {
    while !rpc_queue::empty() {}
    send(&RpcSend {
        async:   false,
        service: service,
        tag:     tag.as_ref(),
        data:    data
    })
}

extern fn send_async_rpc(service: u32, tag: CSlice<u8>, data: *const *const ()) {
    while rpc_queue::full() {}
    rpc_queue::enqueue(|mut slice| {
        let length = {
            let mut writer = Cursor::new(&mut slice[4..]);
            rpc_proto::send_args(&mut writer, service, tag.as_ref(), data)?;
            writer.position()
        };
        proto::write_u32(&mut slice, length as u32)
    }).unwrap_or_else(|err| {
        assert!(err.kind() == std::io::ErrorKind::WriteZero);

        while !rpc_queue::empty() {}
        send(&RpcSend {
            async:   true,
            service: service,
            tag:     tag.as_ref(),
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
                                mut backtrace: CMutSlice<usize>) -> ! {
    let mut cursor = 0;
    for index in 0..backtrace.len() {
        if backtrace[index] > kernel_proto::KERNELCPU_PAYLOAD_ADDRESS {
            backtrace[cursor] = backtrace[index] - kernel_proto::KERNELCPU_PAYLOAD_ADDRESS;
            cursor += 1;
        }
    }
    let backtrace = &mut backtrace.as_mut()[0..cursor];

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

extern fn cache_get(key: CSlice<u8>) -> CSlice<'static, i32> {
    send(&CacheGetRequest {
        key:   str::from_utf8(key.as_ref()).unwrap()
    });
    recv!(&CacheGetReply { value } => value.as_c_slice())
}

extern fn cache_put(key: CSlice<u8>, list: CSlice<i32>) {
    send(&CachePutRequest {
        key:   str::from_utf8(key.as_ref()).unwrap(),
        value: list.as_ref()
    });
    recv!(&CachePutReply { succeeded } => {
        if !succeeded {
            artiq_raise!("CacheError", "cannot put into a busy cache row")
        }
    })
}

extern fn i2c_start(busno: i32) {
    send(&I2CStartRequest { busno: busno as u8 });
}

extern fn i2c_stop(busno: i32) {
    send(&I2CStopRequest { busno: busno as u8 });
}

extern fn i2c_write(busno: i32, data: i32) -> bool {
    send(&I2CWriteRequest { busno: busno as u8, data: data as u8 });
    recv!(&I2CWriteReply { ack } => ack)
}

extern fn i2c_read(busno: i32, ack: bool) -> i32 {
    send(&I2CReadRequest { busno: busno as u8, ack: ack });
    recv!(&I2CReadReply { data } => data) as i32
}

unsafe fn attribute_writeback(typeinfo: *const ()) {
    struct Attr {
        offset: usize,
        tag:    CSlice<'static, u8>,
        name:   CSlice<'static, u8>
    }

    struct Type {
        attributes: *const *const Attr,
        objects:    *const *const ()
    }

    // artiq_compile'd kernels don't include type information
    if typeinfo.is_null() { return }

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

                if (*attribute).tag.len() > 0 {
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

    attribute_writeback(library.lookup("typeinfo") as *const ());

    send(&RunFinished);

    loop {}
}

#[no_mangle]
pub fn exception_handler(vect: u32, _regs: *const u32, pc: u32, ea: u32) {
    println!("exception {:?} at PC 0x{:x}, EA 0x{:x}", vect, pc, ea);
    send(&RunAborted)
}
