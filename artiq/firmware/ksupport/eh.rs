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
#![allow(non_upper_case_globals, non_camel_case_types, dead_code)]

use core::{ptr, mem};
use cslice::CSlice;
use unwind as uw;
use libc::{c_int, c_void};

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

const DW_EH_PE_omit: u8 = 0xFF;
const DW_EH_PE_absptr: u8 = 0x00;

const DW_EH_PE_uleb128: u8 = 0x01;
const DW_EH_PE_udata2: u8 = 0x02;
const DW_EH_PE_udata4: u8 = 0x03;
const DW_EH_PE_udata8: u8 = 0x04;
const DW_EH_PE_sleb128: u8 = 0x09;
const DW_EH_PE_sdata2: u8 = 0x0A;
const DW_EH_PE_sdata4: u8 = 0x0B;
const DW_EH_PE_sdata8: u8 = 0x0C;

const DW_EH_PE_pcrel: u8 = 0x10;
const DW_EH_PE_textrel: u8 = 0x20;
const DW_EH_PE_datarel: u8 = 0x30;
const DW_EH_PE_funcrel: u8 = 0x40;
const DW_EH_PE_aligned: u8 = 0x50;

const DW_EH_PE_indirect: u8 = 0x80;

#[derive(Clone)]
struct DwarfReader {
    pub ptr: *const u8,
}

impl DwarfReader {
    fn new(ptr: *const u8) -> DwarfReader {
        DwarfReader { ptr: ptr }
    }

    // DWARF streams are packed, so e.g. a u32 would not necessarily be aligned
    // on a 4-byte boundary. This may cause problems on platforms with strict
    // alignment requirements. By wrapping data in a "packed" struct, we are
    // telling the backend to generate "misalignment-safe" code.
    unsafe fn read<T: Copy>(&mut self) -> T {
        let result = ptr::read_unaligned(self.ptr as *const T);
        self.ptr = self.ptr.offset(mem::size_of::<T>() as isize);
        result
    }

    // ULEB128 and SLEB128 encodings are defined in Section 7.6 - "Variable
    // Length Data".
    unsafe fn read_uleb128(&mut self) -> u64 {
        let mut shift: usize = 0;
        let mut result: u64 = 0;
        let mut byte: u8;
        loop {
            byte = self.read::<u8>();
            result |= ((byte & 0x7F) as u64) << shift;
            shift += 7;
            if byte & 0x80 == 0 {
                break;
            }
        }
        result
    }

    unsafe fn read_sleb128(&mut self) -> i64 {
        let mut shift: usize = 0;
        let mut result: u64 = 0;
        let mut byte: u8;
        loop {
            byte = self.read::<u8>();
            result |= ((byte & 0x7F) as u64) << shift;
            shift += 7;
            if byte & 0x80 == 0 {
                break;
            }
        }
        // sign-extend
        if shift < 8 * mem::size_of::<u64>() && (byte & 0x40) != 0 {
            result |= (!0 as u64) << shift;
        }
        result as i64
    }

    unsafe fn read_encoded_pointer(&mut self, encoding: u8) -> usize {
        fn round_up(unrounded: usize, align: usize) -> usize {
            debug_assert!(align.is_power_of_two());
            (unrounded + align - 1) & !(align - 1)
        }

        debug_assert!(encoding != DW_EH_PE_omit);

        // DW_EH_PE_aligned implies it's an absolute pointer value
        if encoding == DW_EH_PE_aligned {
            self.ptr = round_up(self.ptr as usize, mem::size_of::<usize>()) as *const u8;
            return self.read::<usize>()
        }

        let value_ptr = self.ptr;
        let mut result = match encoding & 0x0F {
            DW_EH_PE_absptr => self.read::<usize>(),
            DW_EH_PE_uleb128 => self.read_uleb128() as usize,
            DW_EH_PE_udata2 => self.read::<u16>() as usize,
            DW_EH_PE_udata4 => self.read::<u32>() as usize,
            DW_EH_PE_udata8 => self.read::<u64>() as usize,
            DW_EH_PE_sleb128 => self.read_sleb128() as usize,
            DW_EH_PE_sdata2 => self.read::<i16>() as usize,
            DW_EH_PE_sdata4 => self.read::<i32>() as usize,
            DW_EH_PE_sdata8 => self.read::<i64>() as usize,
            _ => panic!(),
        };

        result += match encoding & 0x70 {
            DW_EH_PE_absptr => 0,
            // relative to address of the encoded value, despite the name
            DW_EH_PE_pcrel => value_ptr as usize,
            _ => panic!(),
        };

        if encoding & DW_EH_PE_indirect != 0 {
            result = *(result as *const usize);
        }

        result
    }
}

fn encoding_size(encoding: u8) -> usize {
    if encoding == DW_EH_PE_omit {
        return 0
    }

    match encoding & 0x0F {
        DW_EH_PE_absptr => mem::size_of::<usize>(),
        DW_EH_PE_udata2 => 2,
        DW_EH_PE_udata4 => 4,
        DW_EH_PE_udata8 => 8,
        DW_EH_PE_sdata2 => 2,
        DW_EH_PE_sdata4 => 4,
        DW_EH_PE_sdata8 => 8,
        _ => panic!()
    }
}

pub enum EHAction {
    None,
    Cleanup(usize),
    Catch(usize),
    Terminate,
}

unsafe fn find_eh_action(lsda: *const u8, func_start: usize, ip: usize,
                         exn_name: CSlice<u8>) -> EHAction {
    if lsda.is_null() {
        return EHAction::None
    }

    let mut reader = DwarfReader::new(lsda);

    let start_encoding = reader.read::<u8>();
    // base address for landing pad offsets
    let lpad_base = if start_encoding != DW_EH_PE_omit {
        reader.read_encoded_pointer(start_encoding)
    } else {
        func_start
    };

    let ttype_encoding = reader.read::<u8>();
    let ttype_encoding_size = encoding_size(ttype_encoding) as isize;

    let class_info;
    if ttype_encoding != DW_EH_PE_omit {
        let class_info_offset = reader.read_uleb128();
        class_info = reader.ptr.offset(class_info_offset as isize);
    } else {
        class_info = ptr::null();
    }
    assert!(!class_info.is_null());

    let call_site_encoding = reader.read::<u8>();
    let call_site_table_length = reader.read_uleb128();
    let action_table = reader.ptr.offset(call_site_table_length as isize);

    while reader.ptr < action_table {
        let cs_start = reader.read_encoded_pointer(call_site_encoding);
        let cs_len = reader.read_encoded_pointer(call_site_encoding);
        let cs_lpad = reader.read_encoded_pointer(call_site_encoding);
        let cs_action = reader.read_uleb128();

        if ip < func_start + cs_start {
            // Callsite table is sorted by cs_start, so if we've passed the ip, we
            // may stop searching.
            break
        }
        if ip > func_start + cs_start + cs_len {
            continue
        }

        if cs_lpad == 0 {
            return EHAction::None
        }

        let lpad = lpad_base + cs_lpad;
        if cs_action == 0 {
            return EHAction::Cleanup(lpad)
        }

        let action_entry = action_table.offset((cs_action - 1) as isize);
        let mut action_reader = DwarfReader::new(action_entry);
        loop {
            let type_info_offset = action_reader.read_sleb128() as isize;
            let action_offset = action_reader.clone().read_sleb128() as isize;
            assert!(type_info_offset >= 0);

            if type_info_offset > 0 {
                let type_info_ptr_ptr = class_info.offset(-type_info_offset * ttype_encoding_size);
                let type_info_ptr = DwarfReader::new(type_info_ptr_ptr)
                                                .read_encoded_pointer(ttype_encoding);
                let type_info = *(type_info_ptr as *const CSlice<u8>);

                if type_info.as_ref() == exn_name.as_ref() {
                    return EHAction::Catch(lpad)
                }

                if type_info.len() == 0 {
                    // This is a catch-all clause. We don't compare type_info_ptr with null here
                    // because, in PIC mode, the OR1K LLVM backend emits a literal zero
                    // encoded with DW_EH_PE_pcrel, which of course doesn't result in
                    // a proper null pointer.
                    return EHAction::Catch(lpad)
                }
            }

            if action_offset == 0 {
                break
            } else {
                action_reader.ptr = action_reader.ptr.offset(action_offset)
            }
        }

        return EHAction::None
    }

    // the function has a personality but no landing pads; this is fine
    EHAction::None
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

        let eh_action = find_eh_action(lsda, func_start, ip, exception.name);
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
    handled:        false,
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
    if INFLIGHT.handled {
        raise(&INFLIGHT.exception.unwrap())
    } else {
        uw::_Unwind_Resume(&mut INFLIGHT.uw_exception)
    }
}

// Stub implementations for the functions the panic_unwind crate expects to be provided.
// These all do nothing in libunwind, but aren't built for OR1K.
pub mod stubs {
    #![allow(bad_style, unused_variables)]

    use super::{uw, c_int};

    #[export_name="_Unwind_GetIPInfo"]
    pub unsafe extern fn _Unwind_GetIPInfo(ctx: *mut uw::_Unwind_Context,
                                           ip_before_insn: *mut c_int) -> uw::_Unwind_Word {
        *ip_before_insn = 0;
        uw::_Unwind_GetIP(ctx)
    }

    #[export_name="_Unwind_GetTextRelBase"]
    pub unsafe extern fn _Unwind_GetTextRelBase(ctx: *mut uw::_Unwind_Context) -> uw::_Unwind_Ptr {
        unimplemented!()
    }

    #[export_name="_Unwind_GetDataRelBase"]
    pub unsafe extern fn _Unwind_GetDataRelBase(ctx: *mut uw::_Unwind_Context) -> uw::_Unwind_Ptr {
        unimplemented!()
    }
}
