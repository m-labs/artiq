#![feature(lang_items, asm, libc, panic_unwind, unwind_attributes, global_allocator)]
#![no_std]

extern crate byteorder;
extern crate cslice;
extern crate unwind;
extern crate libc;

extern crate alloc_stub;
extern crate std_artiq as std;
extern crate board;
extern crate dyld;
extern crate proto;
extern crate amp;

use core::{mem, ptr, slice, str};
use std::io::Cursor;
use cslice::{CSlice, AsCSlice};
use alloc_stub::StubAlloc;
use board::csr;
use dyld::Library;
use proto::{kernel_proto, rpc_proto};
use proto::kernel_proto::*;
use amp::{mailbox, rpc_queue};

#[global_allocator]
static mut ALLOC: StubAlloc = StubAlloc;

fn send(request: &Message) {
    unsafe { mailbox::send(request as *const _ as usize) }
    while !mailbox::acknowledged() {}
}

fn recv<R, F: FnOnce(&Message) -> R>(f: F) -> R {
    while mailbox::receive() == 0 {}
    let result = f(unsafe { &*(mailbox::receive() as *const Message) });
    mailbox::acknowledge();
    result
}

macro_rules! recv {
    ($p:pat => $e:expr) => {
        recv(move |request| {
            if let $p = request {
                $e
            } else {
                send(&Log(format_args!("unexpected reply: {:?}\n", request)));
                loop {}
            }
        })
    }
}

#[no_mangle]
#[lang = "panic_fmt"]
pub extern fn panic_fmt(args: core::fmt::Arguments, file: &'static str, line: u32) -> ! {
    send(&Log(format_args!("panic at {}:{}: {}\n", file, line, args)));
    send(&RunAborted);
    loop {}
}

macro_rules! print {
    ($($arg:tt)*) => ($crate::send(&$crate::kernel_proto::Log(format_args!($($arg)*))));
}

macro_rules! println {
    ($fmt:expr) => (print!(concat!($fmt, "\n")));
    ($fmt:expr, $($arg:tt)*) => (print!(concat!($fmt, "\n"), $($arg)*));
}

macro_rules! raise {
    ($name:expr, $message:expr, $param0:expr, $param1:expr, $param2:expr) => ({
        use cslice::AsCSlice;
        let exn = $crate::eh::Exception {
            name:     concat!("0:artiq.coredevice.exceptions.", $name).as_bytes().as_c_slice(),
            file:     file!().as_bytes().as_c_slice(),
            line:     line!(),
            column:   column!(),
            // https://github.com/rust-lang/rfcs/pull/1719
            function: "(Rust function)".as_bytes().as_c_slice(),
            message:  $message.as_bytes().as_c_slice(),
            param:    [$param0, $param1, $param2]
        };
        #[allow(unused_unsafe)]
        unsafe { $crate::eh::raise(&exn) }
    });
    ($name:expr, $message:expr) => ({
        raise!($name, $message, 0, 0, 0)
    });
}

pub mod eh;
mod api;
mod rtio;
mod nrt_bus;

static mut NOW: u64 = 0;
static mut LIBRARY: Option<Library<'static>> = None;

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

extern fn rpc_send(service: u32, tag: CSlice<u8>, data: *const *const ()) {
    while !rpc_queue::empty() {}
    send(&RpcSend {
        async:   false,
        service: service,
        tag:     tag.as_ref(),
        data:    data
    })
}

extern fn rpc_send_async(service: u32, tag: CSlice<u8>, data: *const *const ()) {
    while rpc_queue::full() {}
    rpc_queue::enqueue(|mut slice| {
        let length = {
            let mut writer = Cursor::new(&mut slice[4..]);
            rpc_proto::send_args(&mut writer, service, tag.as_ref(), data)?;
            writer.position()
        };
        proto::WriteExt::write_u32(&mut slice, length as u32)
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

extern fn rpc_recv(slot: *mut ()) -> usize {
    send(&RpcRecvRequest(slot));
    recv!(&RpcRecvReply(ref result) => {
        match result {
            &Ok(alloc_size) => alloc_size,
            &Err(ref exception) =>
            unsafe {
                eh::raise(&eh::Exception {
                    name:     exception.name.as_bytes().as_c_slice(),
                    file:     exception.file.as_bytes().as_c_slice(),
                    line:     exception.line,
                    column:   exception.column,
                    function: exception.function.as_bytes().as_c_slice(),
                    message:  exception.message.as_bytes().as_c_slice(),
                    param:    exception.param
                })
            }
        }
    })
}

fn terminate(exception: &eh::Exception, backtrace: &mut [usize]) -> ! {
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
        exception: kernel_proto::Exception {
            name:     str::from_utf8(exception.name.as_ref()).unwrap(),
            file:     str::from_utf8(exception.file.as_ref()).unwrap(),
            line:     exception.line,
            column:   exception.column,
            function: str::from_utf8(exception.function.as_ref()).unwrap(),
            message:  str::from_utf8(exception.message.as_ref()).unwrap(),
            param:    exception.param,
        },
        backtrace: backtrace
    });
    loop {}
}

extern fn watchdog_set(ms: i64) -> i32 {
    if ms < 0 {
        raise!("ValueError", "cannot set a watchdog with a negative timeout")
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
            raise!("CacheError", "cannot put into a busy cache row")
        }
    })
}

const DMA_BUFFER_SIZE: usize = 64 * 1024;

struct DmaRecorder {
    active:   bool,
    #[allow(dead_code)]
    padding:  [u8; 3], //https://github.com/rust-lang/rust/issues/41315
    data_len: usize,
    buffer:   [u8; DMA_BUFFER_SIZE],
}

static mut DMA_RECORDER: DmaRecorder = DmaRecorder {
    active:   false,
    padding:  [0; 3],
    data_len: 0,
    buffer:   [0; DMA_BUFFER_SIZE],
};

fn dma_record_flush() {
    unsafe {
        send(&DmaRecordAppend(&DMA_RECORDER.buffer[..DMA_RECORDER.data_len]));
        DMA_RECORDER.data_len = 0;
    }
}

extern fn dma_record_start(name: CSlice<u8>) {
    let name = str::from_utf8(name.as_ref()).unwrap();

    unsafe {
        if DMA_RECORDER.active {
            raise!("DMAError", "DMA is already recording")
        }

        let library = LIBRARY.as_ref().unwrap();
        library.rebind(b"rtio_output",
                       dma_record_output as *const () as u32).unwrap();
        library.rebind(b"rtio_output_wide",
                       dma_record_output_wide as *const () as u32).unwrap();

        DMA_RECORDER.active = true;
        send(&DmaRecordStart(name));
    }
}

extern fn dma_record_stop(duration: i64) {
    unsafe {
        dma_record_flush();

        if !DMA_RECORDER.active {
            raise!("DMAError", "DMA is not recording")
        }

        let library = LIBRARY.as_ref().unwrap();
        library.rebind(b"rtio_output",
                       rtio::output as *const () as u32).unwrap();
        library.rebind(b"rtio_output_wide",
                       rtio::output_wide as *const () as u32).unwrap();

        DMA_RECORDER.active = false;
        send(&DmaRecordStop {
            duration: duration as u64
        });
    }
}

extern fn dma_record_output(timestamp: i64, channel: i32, address: i32, word: i32) {
    dma_record_output_wide(timestamp, channel, address, [word].as_c_slice())
}

extern fn dma_record_output_wide(timestamp: i64, channel: i32, address: i32, words: CSlice<i32>) {
    assert!(words.len() <= 16); // enforce the hardware limit

    // See gateware/rtio/dma.py.
    let header_length = /*length*/1 + /*channel*/3 + /*timestamp*/8 + /*address*/2;
    let length = header_length + /*data*/words.len() * 4;

    let header = [
        (length    >>  0) as u8,
        (channel   >>  0) as u8,
        (channel   >>  8) as u8,
        (channel   >> 16) as u8,
        (timestamp >>  0) as u8,
        (timestamp >>  8) as u8,
        (timestamp >> 16) as u8,
        (timestamp >> 24) as u8,
        (timestamp >> 32) as u8,
        (timestamp >> 40) as u8,
        (timestamp >> 48) as u8,
        (timestamp >> 56) as u8,
        (address   >>  0) as u8,
        (address   >>  8) as u8,
    ];

    let mut data = [0; 16 * 4];
    for (i, &word) in words.as_ref().iter().enumerate() {
        let part = [
            (word >>  0) as u8,
            (word >>  8) as u8,
            (word >> 16) as u8,
            (word >> 24) as u8,
        ];
        data[i * 4..(i + 1) * 4].copy_from_slice(&part[..]);
    }
    let data = &data[..words.len() * 4];

    unsafe {
        if DMA_RECORDER.buffer.len() - DMA_RECORDER.data_len < length {
            dma_record_flush()
        }
        let dst = &mut DMA_RECORDER.buffer[DMA_RECORDER.data_len..
                                           DMA_RECORDER.data_len + length];
        dst[..header_length].copy_from_slice(&header[..]);
        dst[header_length..].copy_from_slice(&data[..]);
        DMA_RECORDER.data_len += length;
    }
}

extern fn dma_erase(name: CSlice<u8>) {
    let name = str::from_utf8(name.as_ref()).unwrap();

    send(&DmaEraseRequest { name: name });
}

#[repr(C)]
struct DmaTrace {
    duration: i64,
    address:  i32,
}

extern fn dma_retrieve(name: CSlice<u8>) -> DmaTrace {
    let name = str::from_utf8(name.as_ref()).unwrap();

    send(&DmaRetrieveRequest { name: name });
    recv!(&DmaRetrieveReply { trace, duration } => {
        match trace {
            Some(bytes) => Ok(DmaTrace {
                address:  bytes.as_ptr() as i32,
                duration: duration as i64
            }),
            None => Err(())
        }
    }).unwrap_or_else(|()| {
        println!("DMA trace called {:?} not found", name);
        raise!("DMAError",
            "DMA trace not found");
    })
}

#[cfg(has_rtio)]
extern fn dma_playback(timestamp: i64, ptr: i32) {
    assert!(ptr % 64 == 0);

    unsafe {
        csr::rtio_dma::base_address_write(ptr as u64);
        csr::rtio_dma::time_offset_write(timestamp as u64);

        csr::cri_con::selected_write(1);
        csr::rtio_dma::enable_write(1);
        while csr::rtio_dma::enable_read() != 0 {}
        csr::cri_con::selected_write(0);

        let error = csr::rtio_dma::error_read();
        if error != 0 {
            let timestamp = csr::rtio_dma::error_timestamp_read();
            let channel = csr::rtio_dma::error_channel_read();
            csr::rtio_dma::error_write(1);
            if error & 1 != 0 {
                raise!("RTIOUnderflow",
                    "RTIO underflow at {0} mu, channel {1}",
                    timestamp as i64, channel as i64, 0);
            }
            if error & 2 != 0 {
                raise!("RTIOLinkError",
                    "RTIO output link error at {0} mu, channel {1}",
                    timestamp as i64, channel as i64, 0);
            }
        }
    }
}

#[cfg(not(has_rtio))]
extern fn dma_playback(timestamp: i64, ptr: i32) {
    unimplemented!("not(has_rtio)")
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
                    rpc_send_async(0, (*attribute).tag, [
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
    let image = slice::from_raw_parts_mut(kernel_proto::KERNELCPU_PAYLOAD_ADDRESS as *mut u8,
                                          kernel_proto::KERNELCPU_LAST_ADDRESS -
                                          kernel_proto::KERNELCPU_PAYLOAD_ADDRESS);

    let library = recv!(&LoadRequest(library) => {
        match Library::load(library, image, &api::resolve) {
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

    let __bss_start = library.lookup(b"__bss_start").unwrap();
    let _end = library.lookup(b"_end").unwrap();
    let __modinit__ = library.lookup(b"__modinit__").unwrap();
    let typeinfo = library.lookup(b"typeinfo");

    LIBRARY = Some(library);

    ptr::write_bytes(__bss_start as *mut u8, 0, (_end - __bss_start) as usize);

    send(&NowInitRequest);
    recv!(&NowInitReply(now) => NOW = now);
    (mem::transmute::<u32, fn()>(__modinit__))();
    send(&NowSave(NOW));

    if let Some(typeinfo) = typeinfo {
        attribute_writeback(typeinfo as *const ());
    }

    send(&RunFinished);

    loop {}
}

#[no_mangle]
pub extern fn exception(vect: u32, _regs: *const u32, pc: u32, ea: u32) {
    panic!("exception {:?} at PC 0x{:x}, EA 0x{:x}", vect, pc, ea)
}

#[no_mangle]
pub extern fn abort() {
    panic!("aborted")
}
