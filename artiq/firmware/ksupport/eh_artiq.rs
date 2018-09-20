// Portions of the code in this file are derived from code by:
//
// Copyright 2015 The Rust Project Developers. See the COPYRIGHT
// file at http://rust-lang.org/COPYRIGHT.
//
// Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
// http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
// <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
// option. This file may not be copied, modified, or distributed
// except according to those terms.
#![allow(private_no_mangle_fns, non_camel_case_types)]

use core::{ptr, mem};
use cslice::CSlice;
use unwind as uw;
use libc::{c_int, c_void};

use eh::dwarf::{self, EHAction};

type _Unwind_Stop_Fn = extern "C" fn(version: c_int,
                                     actions: uw::_Unwind_Action,
                                     exception_class: uw::_Unwind_Exception_Class,
                                     exception_object: *mut uw::_Unwind_Exception,
                                     context: *mut uw::_Unwind_Context,
                                     stop_parameter: *mut c_void)
                                    -> uw::_Unwind_Reason_Code;
extern {
    fn _Unwind_ForcedUnwind(exception: *mut uw::_Unwind_Exception,
                            stop_fn: _Unwind_Stop_Fn,
                            stop_parameter: *mut c_void) -> uw::_Unwind_Reason_Code;
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Exception<'a> {
    pub name:     CSlice<'a, u8>,
    pub file:     CSlice<'a, u8>,
    pub line:     u32,
    pub column:   u32,
    pub function: CSlice<'a, u8>,
    pub message:  CSlice<'a, u8>,
    pub param:    [i64; 3]
}

const EXCEPTION_CLASS: uw::_Unwind_Exception_Class = 0x4d_4c_42_53_41_52_54_51; /* 'MLBSARTQ' */

const MAX_BACKTRACE_SIZE: usize = 128;

#[repr(C)]
struct ExceptionInfo {
    uw_exception:   uw::_Unwind_Exception,
    exception:      Option<Exception<'static>>,
    handled:        bool,
    backtrace:      [usize; MAX_BACKTRACE_SIZE],
    backtrace_size: usize
}

#[cfg(target_arch = "x86_64")]
const UNWIND_DATA_REG: (i32, i32) = (0, 1); // RAX, RDX

#[cfg(any(target_arch = "or1k"))]
const UNWIND_DATA_REG: (i32, i32) = (3, 4); // R3, R4

#[export_name="__artiq_personality"]
pub extern fn personality(version: c_int,
                          actions: uw::_Unwind_Action,
                          uw_exception_class: uw::_Unwind_Exception_Class,
                          uw_exception: *mut uw::_Unwind_Exception,
                          context: *mut uw::_Unwind_Context)
                         -> uw::_Unwind_Reason_Code {
    unsafe {
        if version != 1 || uw_exception_class != EXCEPTION_CLASS {
            return uw::_URC_FATAL_PHASE1_ERROR
        }

        let lsda = uw::_Unwind_GetLanguageSpecificData(context) as *const u8;
        let ip = uw::_Unwind_GetIP(context) - 1;
        let func_start = uw::_Unwind_GetRegionStart(context);

        let exception_info = &mut *(uw_exception as *mut ExceptionInfo);
        let exception = &exception_info.exception.unwrap();

        let eh_action = dwarf::find_eh_action(lsda, func_start, ip, exception.name);
        if actions as u32 & uw::_UA_SEARCH_PHASE as u32 != 0 {
            match eh_action {
                EHAction::None |
                EHAction::Cleanup(_) => return uw::_URC_CONTINUE_UNWIND,
                EHAction::Catch(_) => return uw::_URC_HANDLER_FOUND,
                EHAction::Terminate => return uw::_URC_FATAL_PHASE1_ERROR,
            }
        } else {
            match eh_action {
                EHAction::None => return uw::_URC_CONTINUE_UNWIND,
                EHAction::Cleanup(lpad) |
                EHAction::Catch(lpad) => {
                    if actions as u32 & uw::_UA_HANDLER_FRAME as u32 != 0 {
                        exception_info.handled = true
                    }

                    // Pass a pair of the unwinder exception and ARTIQ exception
                    // (which immediately follows).
                    uw::_Unwind_SetGR(context, UNWIND_DATA_REG.0,
                                      uw_exception as uw::_Unwind_Word);
                    uw::_Unwind_SetGR(context, UNWIND_DATA_REG.1,
                                      exception as *const _ as uw::_Unwind_Word);
                    uw::_Unwind_SetIP(context, lpad);
                    return uw::_URC_INSTALL_CONTEXT;
                }
                EHAction::Terminate => return uw::_URC_FATAL_PHASE2_ERROR,
            }
        }
    }
}

extern fn cleanup(_unwind_code: uw::_Unwind_Reason_Code,
                  uw_exception: *mut uw::_Unwind_Exception) {
    unsafe {
        let exception_info = &mut *(uw_exception as *mut ExceptionInfo);

        exception_info.exception = None;
    }
}

extern fn uncaught_exception(_version: c_int,
                             actions: uw::_Unwind_Action,
                             _uw_exception_class: uw::_Unwind_Exception_Class,
                             uw_exception: *mut uw::_Unwind_Exception,
                             context: *mut uw::_Unwind_Context,
                             _stop_parameter: *mut c_void)
                            -> uw::_Unwind_Reason_Code {
    unsafe {
        let exception_info = &mut *(uw_exception as *mut ExceptionInfo);

        if exception_info.backtrace_size < exception_info.backtrace.len() {
            let ip = uw::_Unwind_GetIP(context);
            exception_info.backtrace[exception_info.backtrace_size] = ip;
            exception_info.backtrace_size += 1;
        }

        if actions as u32 & uw::_UA_END_OF_STACK as u32 != 0 {
            ::terminate(&exception_info.exception.unwrap(),
                        exception_info.backtrace[..exception_info.backtrace_size].as_mut())
        } else {
            uw::_URC_NO_REASON
        }
    }
}

// We can unfortunately not use mem::zeroed in a static, so Option<> is used as a workaround.
// See https://github.com/rust-lang/rust/issues/39498.
static mut INFLIGHT: ExceptionInfo = ExceptionInfo {
    uw_exception: uw::_Unwind_Exception {
        exception_class:   EXCEPTION_CLASS,
        exception_cleanup: cleanup,
        private:           [0; uw::unwinder_private_data_size],
    },
    exception:      None,
    handled:        true,
    backtrace:      [0; MAX_BACKTRACE_SIZE],
    backtrace_size: 0
};

#[export_name="__artiq_raise"]
#[unwind(allowed)]
pub unsafe extern fn raise(exception: *const Exception) -> ! {
    // Zing! The Exception<'a> to Exception<'static> transmute is not really sound in case
    // the exception is ever captured. Fortunately, they currently aren't, and we save
    // on the hassle of having to allocate exceptions somewhere except on stack.
    INFLIGHT.exception = Some(mem::transmute::<Exception, Exception<'static>>(*exception));
    INFLIGHT.handled   = false;

    let result = uw::_Unwind_RaiseException(&mut INFLIGHT.uw_exception);
    assert!(result == uw::_URC_END_OF_STACK);

    INFLIGHT.backtrace_size = 0;
    let _result = _Unwind_ForcedUnwind(&mut INFLIGHT.uw_exception,
                                       uncaught_exception, ptr::null_mut());
    unreachable!()
}

#[export_name="__artiq_reraise"]
#[unwind(allowed)]
pub unsafe extern fn reraise() -> ! {
    use cslice::AsCSlice;

    if INFLIGHT.handled {
        match INFLIGHT.exception {
            Some(ref exception) => raise(exception),
            None => raise(&Exception {
                name:     "0:artiq.coredevice.exceptions.RuntimeError".as_c_slice(),
                file:     file!().as_c_slice(),
                line:     line!(),
                column:   column!(),
                // https://github.com/rust-lang/rfcs/pull/1719
                function: "__artiq_reraise".as_c_slice(),
                message:  "No active exception to reraise".as_c_slice(),
                param:    [0, 0, 0]
            })
        }
    } else {
        uw::_Unwind_Resume(&mut INFLIGHT.uw_exception)
    }
}
