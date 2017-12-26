#![feature(libc, panic_unwind)]
#![no_std]

extern crate unwind;
extern crate libc;

use unwind as uw;
use libc::c_void;

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
        match uw::_Unwind_Backtrace(trace::<F>, &mut f as *mut _ as *mut c_void) {
            uw::_URC_NO_REASON => Ok(()),
            err => Err(err)
        }
    }
}
