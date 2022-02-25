// Copyright 2015 The Rust Project Developers. See the COPYRIGHT
// file at the top-level directory of this distribution and at
// http://rust-lang.org/COPYRIGHT.
//
// Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
// http://www.apache.org/licenses/LICENSE-2.0> or the MIT license
// <LICENSE-MIT or http://opensource.org/licenses/MIT>, at your
// option. This file may not be copied, modified, or distributed
// except according to those terms.

// This is the Rust personality function, adapted for use in ARTIQ. We never actually panic
// from Rust or recover from Rust exceptions (there's nothing to catch the panics), but we
// need a personality function to step back through Rust frames in order to make a backtrace.
//
// By design, this personality function is only ever called in the search phase, although
// to keep things simple and close to upstream, it is not modified
use unwind as uw;
use libc::{c_int, uintptr_t};

use dwarf::{self, EHAction, EHContext};

// Register ids were lifted from LLVM's TargetLowering::getExceptionPointerRegister()
// and TargetLowering::getExceptionSelectorRegister() for each architecture,
// then mapped to DWARF register numbers via register definition tables
// (typically <arch>RegisterInfo.td, search for "DwarfRegNum").
// See also http://llvm.org/docs/WritingAnLLVMBackend.html#defining-a-register.

#[cfg(target_arch = "x86")]
const UNWIND_DATA_REG: (i32, i32) = (0, 2); // EAX, EDX

#[cfg(target_arch = "x86_64")]
const UNWIND_DATA_REG: (i32, i32) = (0, 1); // RAX, RDX

#[cfg(any(target_arch = "riscv32"))]
const UNWIND_DATA_REG: (i32, i32) = (10, 11); // X10, X11

// The following code is based on GCC's C and C++ personality routines.  For reference, see:
// https://github.com/gcc-mirror/gcc/blob/master/libstdc++-v3/libsupc++/eh_personality.cc
// https://github.com/gcc-mirror/gcc/blob/trunk/libgcc/unwind-c.c
#[lang = "eh_personality"]
#[no_mangle]
#[allow(unused)]
unsafe extern "C" fn rust_eh_personality(version: c_int,
                                         actions: uw::_Unwind_Action,
                                         exception_class: uw::_Unwind_Exception_Class,
                                         exception_object: *mut uw::_Unwind_Exception,
                                         context: *mut uw::_Unwind_Context)
                                         -> uw::_Unwind_Reason_Code {
    if version != 1 {
        return uw::_URC_FATAL_PHASE1_ERROR;
    }
    let eh_action = match find_eh_action(context) {
        Ok(action) => action,
        Err(_) => return uw::_URC_FATAL_PHASE1_ERROR,
    };
    if actions as i32 & uw::_UA_SEARCH_PHASE as i32 != 0 {
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
                uw::_Unwind_SetGR(context, UNWIND_DATA_REG.0, exception_object as uintptr_t);
                uw::_Unwind_SetGR(context, UNWIND_DATA_REG.1, 0);
                uw::_Unwind_SetIP(context, lpad);
                return uw::_URC_INSTALL_CONTEXT;
            }
            EHAction::Terminate => return uw::_URC_FATAL_PHASE2_ERROR,
        }
    }
}

unsafe fn find_eh_action(context: *mut uw::_Unwind_Context) -> Result<EHAction, ()> {
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
    dwarf::find_eh_action(lsda, &eh_context, 0)
}
