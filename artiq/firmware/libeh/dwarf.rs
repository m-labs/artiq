//! Parsing of GCC-style Language-Specific Data Area (LSDA)
//! For details see:
//!  * <https://refspecs.linuxfoundation.org/LSB_3.0.0/LSB-PDA/LSB-PDA/ehframechpt.html>
//!  * <https://itanium-cxx-abi.github.io/cxx-abi/exceptions.pdf>
//!  * <https://www.airs.com/blog/archives/460>
//!  * <https://www.airs.com/blog/archives/464>
//!
//! A reference implementation may be found in the GCC source tree
//! (`<root>/libgcc/unwind-c.c` as of this writing).

#![allow(non_upper_case_globals)]
#![allow(unused)]

use core::mem;
use cslice::CSlice;

pub const DW_EH_PE_omit: u8 = 0xFF;
pub const DW_EH_PE_absptr: u8 = 0x00;

pub const DW_EH_PE_uleb128: u8 = 0x01;
pub const DW_EH_PE_udata2: u8 = 0x02;
pub const DW_EH_PE_udata4: u8 = 0x03;
pub const DW_EH_PE_udata8: u8 = 0x04;
pub const DW_EH_PE_sleb128: u8 = 0x09;
pub const DW_EH_PE_sdata2: u8 = 0x0A;
pub const DW_EH_PE_sdata4: u8 = 0x0B;
pub const DW_EH_PE_sdata8: u8 = 0x0C;

pub const DW_EH_PE_pcrel: u8 = 0x10;
pub const DW_EH_PE_textrel: u8 = 0x20;
pub const DW_EH_PE_datarel: u8 = 0x30;
pub const DW_EH_PE_funcrel: u8 = 0x40;
pub const DW_EH_PE_aligned: u8 = 0x50;

pub const DW_EH_PE_indirect: u8 = 0x80;

#[derive(Copy, Clone)]
pub struct EHContext<'a> {
    pub ip: usize,                             // Current instruction pointer
    pub func_start: usize,                     // Address of the current function
    pub get_text_start: &'a dyn Fn() -> usize, // Get address of the code section
    pub get_data_start: &'a dyn Fn() -> usize, // Get address of the data section
}

pub struct DwarfReader {
    pub ptr: *const u8,
}

#[repr(C, packed)]
struct Unaligned<T>(T);

impl DwarfReader {
    pub fn new(ptr: *const u8) -> DwarfReader {
        DwarfReader { ptr }
    }

    // DWARF streams are packed, so e.g., a u32 would not necessarily be aligned
    // on a 4-byte boundary. This may cause problems on platforms with strict
    // alignment requirements. By wrapping data in a "packed" struct, we are
    // telling the backend to generate "misalignment-safe" code.
    pub unsafe fn read<T: Copy>(&mut self) -> T {
        let Unaligned(result) = *(self.ptr as *const Unaligned<T>);
        self.ptr = self.ptr.add(mem::size_of::<T>());
        result
    }

    pub unsafe fn offset(&mut self, offset: isize) {
        self.ptr = self.ptr.offset(offset);
    }

    // ULEB128 and SLEB128 encodings are defined in Section 7.6 - "Variable
    // Length Data".
    pub unsafe fn read_uleb128(&mut self) -> u64 {
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

    pub unsafe fn read_sleb128(&mut self) -> i64 {
        let mut shift: u32 = 0;
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
        if shift < u64::BITS && (byte & 0x40) != 0 {
            result |= (!0 as u64) << shift;
        }
        result as i64
    }
}

unsafe fn read_encoded_pointer(
    reader: &mut DwarfReader,
    context: &EHContext<'_>,
    encoding: u8,
) -> Result<usize, ()> {
    read_encoded_pointer_with_base(reader, encoding, get_base(encoding, context)?)
}

unsafe fn read_encoded_pointer_with_base(
    reader: &mut DwarfReader,
    encoding: u8,
    base: usize,
) -> Result<usize, ()> {
    if encoding == DW_EH_PE_omit {
        return Err(());
    }

    let original_ptr = reader.ptr;
    // DW_EH_PE_aligned implies it's an absolute pointer value
    if encoding == DW_EH_PE_aligned {
        reader.ptr = round_up(reader.ptr as usize, mem::size_of::<usize>())? as *const u8;
        return Ok(reader.read::<usize>());
    }

    let mut result = match encoding & 0x0F {
        DW_EH_PE_absptr => reader.read::<usize>(),
        DW_EH_PE_uleb128 => reader.read_uleb128() as usize,
        DW_EH_PE_udata2 => reader.read::<u16>() as usize,
        DW_EH_PE_udata4 => reader.read::<u32>() as usize,
        DW_EH_PE_udata8 => reader.read::<u64>() as usize,
        DW_EH_PE_sleb128 => reader.read_sleb128() as usize,
        DW_EH_PE_sdata2 => reader.read::<i16>() as usize,
        DW_EH_PE_sdata4 => reader.read::<i32>() as usize,
        DW_EH_PE_sdata8 => reader.read::<i64>() as usize,
        _ => return Err(()),
    };

    result += if (encoding & 0x70) == DW_EH_PE_pcrel {
        original_ptr as usize
    } else {
        base
    };

    if encoding & DW_EH_PE_indirect != 0 {
        result = *(result as *const usize);
    }

    Ok(result)
}

#[derive(Debug)]
pub enum EHAction {
    None,
    Cleanup(usize),
    Catch(usize),
    Terminate,
}

pub const USING_SJLJ_EXCEPTIONS: bool = cfg!(all(target_os = "ios", target_arch = "arm"));

fn size_of_encoded_value(encoding: u8) -> usize {
    if encoding == DW_EH_PE_omit {
        0
    } else {
        let encoding = encoding & 0x07;
        match encoding {
            DW_EH_PE_absptr => core::mem::size_of::<*const ()>(),
            DW_EH_PE_udata2 => 2,
            DW_EH_PE_udata4 => 4,
            DW_EH_PE_udata8 => 8,
            _ => unreachable!(),
        }
    }
}

unsafe fn get_ttype_entry(
    offset: usize,
    encoding: u8,
    ttype_base: usize,
    ttype: *const u8,
) -> Result<*const u8, ()> {
    let i = (offset * size_of_encoded_value(encoding)) as isize;
    read_encoded_pointer_with_base(
        &mut DwarfReader::new(ttype.offset(-i)),
        // the DW_EH_PE_pcrel is a hack.
        // It seems that the default encoding is absolute, but we have to take reallocation into
        // account. Unsure if we can fix this in the compiler setting or if this would be affected
        // by updating the compiler
        encoding,
        ttype_base,
    )
    .map(|v| v as *const u8)
}

pub unsafe fn find_eh_action(
    lsda: *const u8,
    context: &EHContext<'_>,
    id: u32,
) -> Result<EHAction, ()> {
    if lsda.is_null() {
        return Ok(EHAction::None);
    }

    let func_start = context.func_start;
    let mut reader = DwarfReader::new(lsda);

    let start_encoding = reader.read::<u8>();
    // base address for landing pad offsets
    let lpad_base = if start_encoding != DW_EH_PE_omit {
        read_encoded_pointer(&mut reader, context, start_encoding)?
    } else {
        func_start
    };

    let ttype_encoding = reader.read::<u8>();
    // we do care about the type table
    let ttype_offset = if ttype_encoding != DW_EH_PE_omit {
        reader.read_uleb128()
    } else {
        0
    };
    let ttype_base = get_base(ttype_encoding, context).unwrap_or(0);
    let ttype_table = reader.ptr.offset(ttype_offset as isize);

    let call_site_encoding = reader.read::<u8>();
    let call_site_table_length = reader.read_uleb128();
    let action_table = reader.ptr.offset(call_site_table_length as isize);
    let ip = context.ip;

    if !USING_SJLJ_EXCEPTIONS {
        while reader.ptr < action_table {
            let cs_start = read_encoded_pointer(&mut reader, context, call_site_encoding)?;
            let cs_len = read_encoded_pointer(&mut reader, context, call_site_encoding)?;
            let cs_lpad = read_encoded_pointer(&mut reader, context, call_site_encoding)?;
            let cs_action = reader.read_uleb128();
            // Callsite table is sorted by cs_start, so if we've passed the ip, we
            // may stop searching.
            if ip < func_start + cs_start {
                break;
            }
            if ip < func_start + cs_start + cs_len {
                // https://github.com/gcc-mirror/gcc/blob/master/libstdc%2B%2B-v3/libsupc%2B%2B/eh_personality.cc#L528
                let lpad = lpad_base + cs_lpad;
                if cs_lpad == 0 {
                    // no cleanups/handler
                    return Ok(EHAction::None);
                } else if cs_action == 0 {
                    return Ok(EHAction::Cleanup(lpad));
                } else {
                    let mut saw_cleanup = false;
                    let mut action_record = action_table.offset(cs_action as isize - 1);
                    loop {
                        let mut reader = DwarfReader::new(action_record);
                        let ar_filter = reader.read_sleb128();
                        action_record = reader.ptr;
                        let ar_disp = reader.read_sleb128();
                        if ar_filter == 0 {
                            saw_cleanup = true;
                        } else if ar_filter > 0 {
                            let catch_type = get_ttype_entry(
                                ar_filter as usize,
                                ttype_encoding,
                                ttype_base,
                                ttype_table,
                            )?;
                            if (catch_type as *const CSlice<u8>).is_null() {
                                return Ok(EHAction::Catch(lpad));
                            }
                            // this seems to be target dependent
                            let clause_id = *(catch_type as *const u32);
                            if clause_id == id {
                                return Ok(EHAction::Catch(lpad));
                            }
                        } else if ar_filter < 0 {
                            // FIXME: how to handle this?
                            break;
                        }
                        if ar_disp == 0 {
                            break;
                        }
                        action_record = action_record.offset((ar_disp as usize) as isize);
                    }
                    if saw_cleanup {
                        return Ok(EHAction::Cleanup(lpad));
                    } else {
                        return Ok(EHAction::None);
                    }
                }
            }
        }
        // Ip is not present in the table.  This should not happen... but it does: issue #35011.
        // So rather than returning EHAction::Terminate, we do this.
        Ok(EHAction::None)
    } else {
        // SjLj version: (not yet modified)
        // The "IP" is an index into the call-site table, with two exceptions:
        // -1 means 'no-action', and 0 means 'terminate'.
        match ip as isize {
            -1 => return Ok(EHAction::None),
            0 => return Ok(EHAction::Terminate),
            _ => (),
        }
        let mut idx = ip;
        loop {
            let cs_lpad = reader.read_uleb128();
            let cs_action = reader.read_uleb128();
            idx -= 1;
            if idx == 0 {
                // Can never have null landing pad for sjlj -- that would have
                // been indicated by a -1 call site index.
                let lpad = (cs_lpad + 1) as usize;
                return Ok(interpret_cs_action(cs_action, lpad));
            }
        }
    }
}

fn interpret_cs_action(cs_action: u64, lpad: usize) -> EHAction {
    if cs_action == 0 {
        // If cs_action is 0 then this is a cleanup (Drop::drop). We run these
        // for both Rust panics and foreign exceptions.
        EHAction::Cleanup(lpad)
    } else {
        // Stop unwinding Rust panics at catch_unwind.
        EHAction::Catch(lpad)
    }
}

#[inline]
fn round_up(unrounded: usize, align: usize) -> Result<usize, ()> {
    if align.is_power_of_two() {
        Ok((unrounded + align - 1) & !(align - 1))
    } else {
        Err(())
    }
}

fn get_base(encoding: u8, context: &EHContext<'_>) -> Result<usize, ()> {
    match encoding & 0x70 {
        DW_EH_PE_absptr | DW_EH_PE_pcrel | DW_EH_PE_aligned => Ok(0),
        DW_EH_PE_textrel => Ok((*context.get_text_start)()),
        DW_EH_PE_datarel => Ok((*context.get_data_start)()),
        DW_EH_PE_funcrel if context.func_start != 0 => Ok(context.func_start),
        _ => return Err(()),
    }
}

