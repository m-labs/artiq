// ARTIQ Exception struct declaration
use cslice::CSlice;

// Note: CSlice within an exception may not be actual cslice, they may be strings that exist only
// in the host. If the length == usize:MAX, the pointer is actually a string key in the host.
#[repr(C)]
#[derive(Copy, Clone)]
pub struct Exception<'a> {
    pub id:       u32,
    pub file:     CSlice<'a, u8>,
    pub line:     u32,
    pub column:   u32,
    pub function: CSlice<'a, u8>,
    pub message:  CSlice<'a, u8>,
    pub param:    [i64; 3]
}

fn str_err(_: core::str::Utf8Error) -> core::fmt::Error {
    core::fmt::Error
}

fn exception_str<'a>(s: &'a CSlice<'a, u8>) -> Result<&'a str, core::str::Utf8Error> {
    if s.len() == usize::MAX {
        Ok("<host string>")
    } else {
        core::str::from_utf8(s.as_ref())
    }
}

impl<'a> core::fmt::Debug for Exception<'a> {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "Exception {} from {} in {}:{}:{}, message: {}",
            self.id,
            exception_str(&self.function).map_err(str_err)?,
            exception_str(&self.file).map_err(str_err)?,
            self.line, self.column,
            exception_str(&self.message).map_err(str_err)?)
    }
}

#[derive(Copy, Clone, Debug, Default)]
pub struct StackPointerBacktrace {
    pub stack_pointer: usize,
    pub initial_backtrace_size: usize,
    pub current_backtrace_size: usize,
}

