#![feature(libc, panic_unwind)]
#![no_std]

extern crate unwind;
extern crate libc;

use unwind as uw;
use libc::{c_void, c_int};

const UW_REG_SP: c_int = -2;

pub fn backtrace<F>(f: F) -> Result<(), uw::_Unwind_Reason_Code>
    where F: FnMut(usize) -> ()
{
    struct TraceContext<F> {
        step_fn: F,
        prev_sp: uw::_Unwind_Word
    }

    extern fn trace<F>(context: *mut uw::_Unwind_Context, arg: *mut c_void)
                      -> uw::_Unwind_Reason_Code
        where F: FnMut(usize) -> ()
    {
        unsafe {
            let trace_context = &mut *(arg as *mut TraceContext<F>);

            // Detect the root of a libfringe thread
            let cur_sp = uw::_Unwind_GetGR(context, UW_REG_SP);
            if cur_sp == trace_context.prev_sp {
                return uw::_URC_END_OF_STACK
            } else {
                trace_context.prev_sp = cur_sp;
            }

            (trace_context.step_fn)(uw::_Unwind_GetIP(context));
            uw::_URC_NO_REASON
        }
    }

    unsafe {
        let mut trace_context = TraceContext { step_fn: f, prev_sp: 0 };
        match uw::_Unwind_Backtrace(trace::<F>, &mut trace_context as *mut _ as *mut c_void) {
            uw::_URC_NO_REASON => Ok(()),
            err => Err(err)
        }
    }
}
