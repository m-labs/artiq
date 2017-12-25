#![feature(libc, panic_unwind, never_type)]
#![allow(non_upper_case_globals, non_camel_case_types)]
#![no_std]

extern crate unwind;
extern crate libc;

use unwind as uw;
use libc::c_void;

type _Unwind_Trace_Fn = extern "C" fn(*mut uw::_Unwind_Context, *mut c_void)
                                     -> uw::_Unwind_Reason_Code;
extern {
    fn _Unwind_Backtrace(trace_fn: _Unwind_Trace_Fn, arg: *mut c_void)
                        -> uw::_Unwind_Reason_Code;
}

pub fn backtrace<F>(mut f: F) -> Result<(), uw::_Unwind_Reason_Code>
    where F: FnMut(usize) -> ()
{
    extern fn trace<F>(context: *mut uw::_Unwind_Context, arg: *mut c_void)
                      -> uw::_Unwind_Reason_Code
        where F: FnMut(usize) -> ()
    {
        unsafe {
            let step_fn = &mut *(arg as *mut F);
            step_fn(uw::_Unwind_GetIP(context));
            uw::_URC_NO_REASON
        }
    }

    unsafe {
        match _Unwind_Backtrace(trace::<F>, &mut f as *mut _ as *mut c_void) {
            uw::_URC_NO_REASON => Ok(()),
            err => Err(err)
        }
    }
}
