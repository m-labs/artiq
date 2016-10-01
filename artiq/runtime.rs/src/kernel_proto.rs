use std::io;
use mailbox;
use kernel;

#[derive(Debug)]
pub struct Exception<'a> {
    pub name:     &'a str,
    pub file:     &'a str,
    pub line:     u32,
    pub column:   u32,
    pub function: &'a str,
    pub message:  &'a str,
    pub param:    [u64; 3],
}

pub use self::c::BacktraceItem;

#[derive(Debug)]
pub enum Message<'a> {
    LoadRequest(&'a [u8]),
    LoadReply   { error: Option<&'a str> },

    NowInitRequest,
    NowInitReply(u64),
    NowSave(u64),

    RunFinished,
    RunException {
        exception: Exception<'a>,
        backtrace: &'a [BacktraceItem]
    },

    WatchdogSetRequest { ms: u64 },
    WatchdogSetReply   { id: usize },
    WatchdogClear      { id: usize },

    RpcSend {
        service: u32,
        tag: &'a [u8],
        data: *const *const ()
    },
    RpcRecvRequest {
        slot: *mut ()
    },
    RpcRecvReply {
        alloc_size: usize,
        exception: Option<Exception<'a>>
    },

    CacheGetRequest { key: &'a str },
    CacheGetReply   { value: &'static [u32] },
    CachePutRequest { key: &'a str, value: &'static [u32] },
    CachePutReply   { succeeded: bool },

    Log(&'a str)
}

pub use self::Message::*;

impl<'a> Message<'a> {
    fn into_lower<R, F: FnOnce(*const ()) -> R>(self, f: F) -> R {
        match self {
            Message::LoadRequest(library) => {
                let msg = c::LoadRequest {
                    ty: c::Type::LoadRequest,
                    library: library.as_ptr() as *const _
                };
                f(&msg as *const _ as *const _)
            }

            Message::NowInitReply(now) => {
                let msg = c::NowInitReply {
                    ty: c::Type::NowInitReply,
                    now: now
                };
                f(&msg as *const _ as *const _)
            }

            other => panic!("Message::into_lower: {:?} unimplemented", other)
        }
    }

    unsafe fn from_lower(ptr: *const ()) -> Self {
        let msg = ptr as *const c::Message;
        match (*msg).ty {
            c::Type::LoadReply => {
                let msg = ptr as *const c::LoadReply;
                let error = if (*msg).error.is_null() {
                    None
                } else {
                    Some(c::from_c_str((*msg).error))
                };
                Message::LoadReply { error: error }
            }

            c::Type::NowInitRequest => Message::NowInitRequest,
            c::Type::NowSave => {
                let msg = ptr as *const c::NowSave;
                Message::NowSave((*msg).now)
            }

            c::Type::RunFinished => Message::RunFinished,

            c::Type::Log => {
                let msg = ptr as *const c::Log;
                Message::Log(c::from_c_str_len((*msg).buf, (*msg).len))
            }

            ref other => panic!("Message::from_lower: {:?} unimplemented", other)
        }
    }

    pub fn send_and_wait(self, waiter: ::sched::Waiter) -> io::Result<()> {
        self.into_lower(|ptr| {
            unsafe { mailbox::send(ptr as usize) }
            waiter.until(mailbox::acknowledged)
        })
    }

    pub fn wait_and_receive<R, F>(waiter: ::sched::Waiter, f: F) -> io::Result<R>
            where F: FnOnce(Message<'a>) -> io::Result<R> {
        try!(waiter.until(|| mailbox::receive() != 0));
        if !kernel::validate(mailbox::receive()) {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "invalid kernel CPU pointer"))
        }

        let msg = unsafe { Self::from_lower(mailbox::receive() as *const ()) };
        Ok(try!(f(msg)))
    }

    pub fn acknowledge() {
        unsafe { mailbox::acknowledge() }
    }
}

// Low-level representation, compatible with the C code in ksupport
mod c {
    use libc::{c_void, c_int, c_char, size_t};

    #[repr(u32)]
    #[derive(Debug)]
    pub enum Type {
        LoadRequest,
        LoadReply,
        NowInitRequest,
        NowInitReply,
        NowSave,
        RunFinished,
        RunException,
        WatchdogSetRequest,
        WatchdogSetReply,
        WatchdogClear,
        RpcSend,
        RpcRecvRequest,
        RpcRecvReply,
        RpcBatch,
        CacheGetRequest,
        CacheGetReply,
        CachePutRequest,
        CachePutReply,
        Log,
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct Message {
        pub ty: Type
    }

    // kernel messages

    #[repr(C)]
    #[derive(Debug)]
    pub struct LoadRequest {
        pub ty: Type,
        pub library: *const c_void,
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct LoadReply {
        pub ty: Type,
        pub error: *const c_char
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct NowInitReply {
        pub ty: Type,
        pub now: u64
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct NowSave {
        pub ty: Type,
        pub now: u64
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct RunException {
        pub ty: Type,
        pub exception: *const Exception,
        pub backtrace: *const BacktraceItem,
        pub backtrace_size: size_t
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct WatchdogSetRequest {
        pub ty: Type,
        pub ms: c_int
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct WatchdogSetReply {
        pub ty: Type,
        pub id: c_int
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct WatchdogClear {
        pub ty: Type,
        pub id: c_int
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct RpcSend {
        pub ty: Type,
        pub service: c_int,
        pub tag: *const c_char,
        pub data: *const *const c_void
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct RpcRecvRequest {
        pub ty: Type,
        pub slot: *mut c_void
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct RpcRecvReply {
        pub ty: Type,
        pub alloc_size: c_int,
        pub exception: *const Exception
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct CacheGetRequest {
        pub ty: Type,
        pub key: *const c_char
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct CacheGetReply {
        pub ty: Type,
        pub length: size_t,
        pub elements: *const u32
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct CachePutRequest {
        pub ty: Type,
        pub key: *const c_char,
        pub length: size_t,
        pub elements: *const u32
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct CachePutReply {
        pub ty: Type,
        pub succeeded: c_int
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct Log {
        pub ty: Type,
        pub buf: *const c_char,
        pub len: size_t
    }

    // Supplementary structures

    #[repr(C)]
    #[derive(Debug)]
    pub struct Exception {
        pub name:     *const c_char, // or typeinfo
        pub file:     *const c_char,
        pub line:     u32,
        pub column:   u32,
        pub function: *const c_char,
        pub message:  *const c_char,
        pub param:    [u64; 3],
    }

    #[repr(C)]
    #[derive(Debug)]
    pub struct BacktraceItem {
        pub function: usize,
        pub offset: usize
    }

    pub unsafe fn from_c_str_len<'a>(ptr: *const c_char, len: size_t) -> &'a str {
        use core::{str, slice};
        str::from_utf8_unchecked(slice::from_raw_parts(ptr as *const u8, len))
    }

    pub unsafe fn from_c_str<'a>(ptr: *const c_char) -> &'a str {
        extern { fn strlen(cs: *const c_char) -> size_t; }
        from_c_str_len(ptr, strlen(ptr))
    }
}
