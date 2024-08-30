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
#![allow(non_camel_case_types)]

use core::mem;
use cslice::AsCSlice;
use unwind as uw;
use libc::{c_int, c_void};

use eh::{self, dwarf::{self, EHAction, EHContext}};

pub type Exception<'a> = eh::eh_artiq::Exception<'a>;
pub type StackPointerBacktrace = eh::eh_artiq::StackPointerBacktrace;

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

pub static mut PAYLOAD_ADDRESS: usize = 0;

const EXCEPTION_CLASS: uw::_Unwind_Exception_Class = 0x4d_4c_42_53_41_52_54_51; /* 'MLBSARTQ' */

const MAX_INFLIGHT_EXCEPTIONS: usize = 10;
const MAX_BACKTRACE_SIZE: usize = 128;

struct ExceptionBuffer {
    // we need n _Unwind_Exception, because each will have their own private data
    uw_exceptions: [uw::_Unwind_Exception; MAX_INFLIGHT_EXCEPTIONS],
    exceptions: [Option<Exception<'static>>; MAX_INFLIGHT_EXCEPTIONS + 1],
    exception_stack: [isize; MAX_INFLIGHT_EXCEPTIONS + 1],
    // nested exceptions will share the backtrace buffer, treated as a tree
    // backtrace contains a tuple of IP and SP
    backtrace: [(usize, usize); MAX_BACKTRACE_SIZE],
    backtrace_size: usize,
    // stack pointers are stored to reconstruct backtrace for each exception
    stack_pointers: [StackPointerBacktrace; MAX_INFLIGHT_EXCEPTIONS + 1],
    // current allocated nested exceptions
    exception_count: usize,
}

const EXCEPTION: uw::_Unwind_Exception = uw::_Unwind_Exception {
    exception_class:   EXCEPTION_CLASS,
    exception_cleanup: cleanup,
    private:           [0; uw::unwinder_private_data_size],
};

static mut EXCEPTION_BUFFER: ExceptionBuffer = ExceptionBuffer {
    uw_exceptions: [EXCEPTION; MAX_INFLIGHT_EXCEPTIONS],
    exceptions: [None; MAX_INFLIGHT_EXCEPTIONS + 1],
    exception_stack: [-1; MAX_INFLIGHT_EXCEPTIONS + 1],
    backtrace: [(0, 0); MAX_BACKTRACE_SIZE],
    backtrace_size: 0,
    stack_pointers: [StackPointerBacktrace {
        stack_pointer: 0,
        initial_backtrace_size: 0,
        current_backtrace_size: 0
    }; MAX_INFLIGHT_EXCEPTIONS + 1],
    exception_count: 0
};

pub unsafe extern fn reset_exception_buffer(payload_addr: usize) {
    EXCEPTION_BUFFER.uw_exceptions = [EXCEPTION; MAX_INFLIGHT_EXCEPTIONS];
    EXCEPTION_BUFFER.exceptions = [None; MAX_INFLIGHT_EXCEPTIONS + 1];
    EXCEPTION_BUFFER.exception_stack = [-1; MAX_INFLIGHT_EXCEPTIONS + 1];
    EXCEPTION_BUFFER.backtrace_size = 0;
    EXCEPTION_BUFFER.exception_count = 0;
    PAYLOAD_ADDRESS = payload_addr;
}

#[cfg(target_arch = "x86_64")]
const UNWIND_DATA_REG: (i32, i32) = (0, 1); // RAX, RDX
#[cfg(target_arch = "x86_64")]
// actually this is not the SP, but frame pointer
// but it serves its purpose, and getting SP will somehow cause segfault...
const UNW_FP_REG: c_int = 12;

#[cfg(any(target_arch = "riscv32"))]
const UNWIND_DATA_REG: (i32, i32) = (10, 11); // X10, X11
#[cfg(any(target_arch = "riscv32"))]
const UNW_FP_REG: c_int = 2;

#[export_name="__artiq_personality"]
pub extern fn personality(version: c_int,
                          _actions: uw::_Unwind_Action,
                          uw_exception_class: uw::_Unwind_Exception_Class,
                          uw_exception: *mut uw::_Unwind_Exception,
                          context: *mut uw::_Unwind_Context)
                         -> uw::_Unwind_Reason_Code {
    unsafe {
        if version != 1 || uw_exception_class != EXCEPTION_CLASS {
            return uw::_URC_FATAL_PHASE1_ERROR
        }

        let lsda = uw::_Unwind_GetLanguageSpecificData(context) as *const u8;
        let mut ip_before_instr: c_int = 0;
        let ip = uw::_Unwind_GetIPInfo(context, &mut ip_before_instr);
        let eh_context = EHContext {
            // The return address points 1 byte past the call instruction,
            // which could be in the next IP range in LSDA range table.
            ip: if ip_before_instr != 0 { ip } else { ip - 1 },
            func_start: uw::_Unwind_GetRegionStart(context),
            get_text_start: &|| uw::_Unwind_GetTextRelBase(context),
            get_data_start: &|| uw::_Unwind_GetDataRelBase(context),
        };

        let index = EXCEPTION_BUFFER.exception_stack[EXCEPTION_BUFFER.exception_count - 1];
        assert!(index != -1);
        let exception = EXCEPTION_BUFFER.exceptions[index as usize].as_ref().unwrap();
        let id = exception.id;

        let eh_action = match dwarf::find_eh_action(lsda, &eh_context, id) {
            Ok(action) => action,
            Err(_) => return uw::_URC_FATAL_PHASE1_ERROR,
        };

        match eh_action {
            EHAction::None => return uw::_URC_CONTINUE_UNWIND,
            EHAction::Cleanup(lpad) |
            EHAction::Catch(lpad) => {
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

#[export_name="__artiq_raise"]
pub unsafe extern "C-unwind" fn raise(exception: *const Exception) -> ! {
    let count = EXCEPTION_BUFFER.exception_count;
    let stack = &mut EXCEPTION_BUFFER.exception_stack;
    let diff = exception as isize - EXCEPTION_BUFFER.exceptions.as_ptr() as isize;
    if 0 <= diff && diff <= (mem::size_of::<Option<Exception>>() * MAX_INFLIGHT_EXCEPTIONS) as isize {
        let index = diff / (mem::size_of::<Option<Exception>>() as isize);
        let mut found = false;
        for i in 0..=MAX_INFLIGHT_EXCEPTIONS + 1 {
            if found {
                if stack[i] == -1 {
                    stack[i - 1] = index;
                    assert!(i == count);
                    break;
                } else {
                    stack[i - 1] = stack[i];
                }
            } else {
                if stack[i] == index {
                    found = true;
                }
            }
        }
        assert!(found);
        let _result = _Unwind_ForcedUnwind(&mut EXCEPTION_BUFFER.uw_exceptions[stack[count - 1] as usize],
                                           stop_fn, core::ptr::null_mut());
    } else {
        if count < MAX_INFLIGHT_EXCEPTIONS {
            let exception = &*exception;
            for (i, slot) in EXCEPTION_BUFFER.exceptions.iter_mut().enumerate() {
                // we should always be able to find a slot
                if slot.is_none() {
                    *slot = Some(
                        *mem::transmute::<*const Exception, *const Exception<'static>>
                        (exception));
                    EXCEPTION_BUFFER.exception_stack[count] = i as isize;
                    EXCEPTION_BUFFER.uw_exceptions[i].private =
                        [0; uw::unwinder_private_data_size];
                    EXCEPTION_BUFFER.stack_pointers[i] = StackPointerBacktrace {
                        stack_pointer: 0,
                        initial_backtrace_size: EXCEPTION_BUFFER.backtrace_size,
                        current_backtrace_size: 0,
                    };
                    EXCEPTION_BUFFER.exception_count += 1;
                    let _result = _Unwind_ForcedUnwind(&mut EXCEPTION_BUFFER.uw_exceptions[i],
                                                       stop_fn, core::ptr::null_mut());
                }
            }
        } else {
            // TODO: better reporting?
            let exception = Exception {
                id:       get_exception_id("RuntimeError"),
                file:     file!().as_c_slice(),
                line:     line!(),
                column:   column!(),
                // https://github.com/rust-lang/rfcs/pull/1719
                function: "__artiq_raise".as_c_slice(),
                message:  "too many nested exceptions".as_c_slice(),
                param:    [0, 0, 0]
            };
            EXCEPTION_BUFFER.exceptions[MAX_INFLIGHT_EXCEPTIONS] = Some(mem::transmute(exception));
            EXCEPTION_BUFFER.stack_pointers[MAX_INFLIGHT_EXCEPTIONS] = Default::default();
            EXCEPTION_BUFFER.exception_count += 1;
            uncaught_exception()
        }
    }
    unreachable!();
}


#[export_name="__artiq_resume"]
pub unsafe extern "C-unwind" fn resume() -> ! {
    assert!(EXCEPTION_BUFFER.exception_count != 0);
    let i = EXCEPTION_BUFFER.exception_stack[EXCEPTION_BUFFER.exception_count - 1];
    assert!(i != -1);
    let _result = _Unwind_ForcedUnwind(&mut EXCEPTION_BUFFER.uw_exceptions[i as usize],
                                       stop_fn, core::ptr::null_mut());
    unreachable!()
}

#[export_name="__artiq_end_catch"]
pub unsafe extern "C-unwind" fn end_catch() {
    let mut count = EXCEPTION_BUFFER.exception_count;
    assert!(count != 0);
    // we remove all exceptions with SP <= current exception SP
    // i.e. the outer exception escapes the finally block
    let index = EXCEPTION_BUFFER.exception_stack[count - 1] as usize;
    EXCEPTION_BUFFER.exception_stack[count - 1] = -1;
    EXCEPTION_BUFFER.exceptions[index] = None;
    let outer_sp = EXCEPTION_BUFFER.stack_pointers
        [index].stack_pointer;
    count -= 1;
    for i in (0..count).rev() {
        let index = EXCEPTION_BUFFER.exception_stack[i];
        assert!(index != -1);
        let index = index as usize;
        let sp = EXCEPTION_BUFFER.stack_pointers[index].stack_pointer;
        if sp >= outer_sp {
            break;
        }
        EXCEPTION_BUFFER.exceptions[index] = None;
        EXCEPTION_BUFFER.exception_stack[i] = -1;
        count -= 1;
    }
    EXCEPTION_BUFFER.exception_count = count;
    EXCEPTION_BUFFER.backtrace_size = if count > 0 {
        let index = EXCEPTION_BUFFER.exception_stack[count - 1];
        assert!(index != -1);
        EXCEPTION_BUFFER.stack_pointers[index as usize].current_backtrace_size
    } else {
        0
    };
}

extern fn cleanup(_unwind_code: uw::_Unwind_Reason_Code,
                  _uw_exception: *mut uw::_Unwind_Exception) {
    unimplemented!()
}

fn uncaught_exception() -> ! {
    unsafe {
        // dump way to reorder the stack
        for i in 0..EXCEPTION_BUFFER.exception_count {
            if EXCEPTION_BUFFER.exception_stack[i] != i as isize {
                // find the correct index
                let index = EXCEPTION_BUFFER.exception_stack
                    .iter()
                    .position(|v| *v == i as isize).unwrap();
                let a = EXCEPTION_BUFFER.exception_stack[index];
                let b = EXCEPTION_BUFFER.exception_stack[i];
                assert!(a != -1 && b != -1);
                core::mem::swap(&mut EXCEPTION_BUFFER.exception_stack[index],
                                &mut EXCEPTION_BUFFER.exception_stack[i]);
                core::mem::swap(&mut EXCEPTION_BUFFER.exceptions[a as usize],
                                &mut EXCEPTION_BUFFER.exceptions[b as usize]);
                core::mem::swap(&mut EXCEPTION_BUFFER.stack_pointers[a as usize],
                                &mut EXCEPTION_BUFFER.stack_pointers[b as usize]);
            }
        }
    }
    unsafe {
        ::terminate(
            EXCEPTION_BUFFER.exceptions[..EXCEPTION_BUFFER.exception_count].as_ref(),
            EXCEPTION_BUFFER.stack_pointers[..EXCEPTION_BUFFER.exception_count].as_ref(),
            EXCEPTION_BUFFER.backtrace[..EXCEPTION_BUFFER.backtrace_size].as_mut())
    }
}


// stop function which would be executed when we unwind each frame
extern fn stop_fn(_version: c_int,
                  actions: uw::_Unwind_Action,
                  _uw_exception_class: uw::_Unwind_Exception_Class,
                  _uw_exception: *mut uw::_Unwind_Exception,
                  context: *mut uw::_Unwind_Context,
                  _stop_parameter: *mut c_void) -> uw::_Unwind_Reason_Code {
    unsafe {
        let backtrace_size = EXCEPTION_BUFFER.backtrace_size;
        if backtrace_size < MAX_BACKTRACE_SIZE {
            let ip = uw::_Unwind_GetIP(context);
            let fp = uw::_Unwind_GetGR(context, UNW_FP_REG);
            if PAYLOAD_ADDRESS == 0 || ip > PAYLOAD_ADDRESS {
                let ip = ip - PAYLOAD_ADDRESS;
                EXCEPTION_BUFFER.backtrace[backtrace_size] = (ip, fp);
                EXCEPTION_BUFFER.backtrace_size += 1;
                let last_index = EXCEPTION_BUFFER.exception_stack[EXCEPTION_BUFFER.exception_count - 1];
                assert!(last_index != -1);
                let sp_info = &mut EXCEPTION_BUFFER.stack_pointers[last_index as usize];
                sp_info.stack_pointer = fp;
                sp_info.current_backtrace_size = backtrace_size + 1;
            }
        }
        if actions as u32 & uw::_UA_END_OF_STACK as u32 != 0 {
            uncaught_exception()
        } else {
            uw::_URC_NO_REASON
        }
    }
}

// Must be kept in sync with `artiq.language.embedding_map`
static EXCEPTION_ID_LOOKUP: [(&str, u32); 22] = [
    ("RTIOUnderflow", 0),
    ("RTIOOverflow", 1),
    ("RTIODestinationUnreachable", 2),
    ("DMAError", 3),
    ("I2CError", 4),
    ("CacheError", 5),
    ("SPIError", 6),
    ("SubkernelError", 7),
    ("AssertionError", 8),
    ("AttributeError", 9),
    ("IndexError", 10),
    ("IOError", 11),
    ("KeyError", 12),
    ("NotImplementedError", 13),
    ("OverflowError", 14),
    ("RuntimeError", 15),
    ("TimeoutError", 16),
    ("TypeError", 17),
    ("ValueError", 18),
    ("ZeroDivisionError", 19),
    ("LinAlgError", 20),
    ("UnwrapNoneError", 21),
];

pub fn get_exception_id(name: &str) -> u32 {
    for (n, id) in EXCEPTION_ID_LOOKUP.iter() {
        if *n == name {
            return *id
        }
    }
    unimplemented!("unallocated internal exception id")
}

/// Takes as input exception id from host
/// Generates a new exception with:
///   * `id` set to `exn_id`
///   * `message` set to corresponding exception name from `EXCEPTION_ID_LOOKUP`
///
/// The message is matched on host to ensure correct exception is being referred 
/// This test checks the synchronization of exception ids for runtime errors
#[no_mangle]
pub extern "C-unwind" fn test_exception_id_sync(exn_id: u32) {
    let message = EXCEPTION_ID_LOOKUP
        .iter()
        .find_map(|&(name, id)| if id == exn_id { Some(name) } else { None })
        .unwrap_or("unallocated internal exception id");
    
    let exn = Exception {
        id:       exn_id,
        file:     file!().as_c_slice(),
        line:     0,
        column:   0,
        function: "test_exception_id_sync".as_c_slice(),
        message:  message.as_c_slice(),
        param:    [0, 0, 0]
    };
    unsafe { raise(&exn) };
}
