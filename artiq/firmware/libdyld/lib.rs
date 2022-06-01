#![no_std]

use core::{mem, ptr, fmt, slice, str, convert};
use elf::*;

pub mod elf;

fn read_unaligned<T: Copy>(data: &[u8], offset: usize) -> Result<T, ()> {
    if data.len() < offset + mem::size_of::<T>() {
        Err(())
    } else {
        let ptr = data.as_ptr().wrapping_offset(offset as isize) as *const T;
        Ok(unsafe { ptr::read_unaligned(ptr) })
    }
}

fn get_ref<T: Copy>(data: &[u8], offset: usize) -> Result<&T, ()> {
    if data.len() < offset + mem::size_of::<T>() {
        Err(())
    } else if (data.as_ptr() as usize + offset) & (mem::align_of::<T>() - 1) != 0 {
        Err(())
    } else {
        let ptr = data.as_ptr().wrapping_offset(offset as isize) as *const T;
        Ok(unsafe { &*ptr })
    }
}

fn get_ref_slice<T: Copy>(data: &[u8], offset: usize, len: usize) -> Result<&[T], ()> {
    if data.len() < offset + mem::size_of::<T>() * len {
        Err(())
    } else if (data.as_ptr() as usize + offset) & (mem::align_of::<T>() - 1) != 0 {
        Err(())
    } else {
        let ptr = data.as_ptr().wrapping_offset(offset as isize) as *const T;
        Ok(unsafe { slice::from_raw_parts(ptr, len) })
    }
}

fn elf_hash(name: &[u8]) -> u32 {
    let mut h: u32 = 0;
    for c in name {
        h = (h << 4) + *c as u32;
        let g = h & 0xf0000000;
        if g != 0 {
            h ^= g >> 24;
            h &= !g;
        }
    }
    h
}

#[derive(Debug)]
pub enum Error<'a> {
    Parsing(&'static str),
    Lookup(&'a [u8])
}

impl<'a> convert::From<&'static str> for Error<'a> {
    fn from(desc: &'static str) -> Error<'a> {
        Error::Parsing(desc)
    }
}

impl<'a> fmt::Display for Error<'a> {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            &Error::Parsing(desc) =>
                write!(f, "parse error: {}", desc),
            &Error::Lookup(sym) =>
                match str::from_utf8(sym) {
                    Ok(sym) => write!(f, "symbol lookup error: {}", sym),
                    Err(_)  => write!(f, "symbol lookup error: {:?}", sym)
                }
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Arch {
    RiscV,
    OpenRisc,
}

pub struct Library<'a> {
    image_off:   Elf32_Addr,
    image_sz:    usize,
    strtab:      &'a [u8],
    symtab:      &'a [Elf32_Sym],
    jmprel:      &'a [Elf32_Rela],
    hash_bucket: &'a [Elf32_Word],
    hash_chain:  &'a [Elf32_Word],
}

impl<'a> Library<'a> {
    pub fn lookup(&self, name: &[u8]) -> Option<Elf32_Word> {
        let hash = elf_hash(name);
        let mut index = self.hash_bucket[hash as usize % self.hash_bucket.len()] as usize;

        loop {
            if index == STN_UNDEF { return None }

            let sym = &self.symtab[index];
            let sym_name_off = sym.st_name as usize;
            match self.strtab.get(sym_name_off..sym_name_off + name.len()) {
                Some(sym_name) if sym_name == name => {
                    if ELF32_ST_BIND(sym.st_info) & STB_GLOBAL == 0 {
                        return None
                    }

                    match sym.st_shndx {
                        SHN_UNDEF => return None,
                        SHN_ABS => return Some(sym.st_value),
                        _ => return Some(self.image_off + sym.st_value)
                    }
                }
                _ => (),
            }

            index = self.hash_chain[index] as usize;
        }
    }

    fn name_starting_at(&self, offset: usize) -> Result<&'a [u8], Error<'a>> {
        let size = self.strtab.iter().skip(offset).position(|&x| x == 0)
                              .ok_or("symbol in symbol table not null-terminated")?;
        Ok(self.strtab.get(offset..offset + size)
                      .ok_or("cannot read symbol name")?)
    }

    fn update_rela(&self, rela: &Elf32_Rela, value: Elf32_Word) -> Result<(), Error<'a>> {
        if rela.r_offset as usize + mem::size_of::<Elf32_Addr>() > self.image_sz {
            return Err("relocation out of image bounds")?
        }

        let ptr = (self.image_off + rela.r_offset) as *mut Elf32_Addr;

        match ELF32_R_TYPE(rela.r_info) {
            R_RISCV_RELATIVE | R_RISCV_32 | R_RISCV_JUMP_SLOT => Ok(unsafe { *ptr = value }),

            R_RISCV_CALL_PLT => {
                Ok(unsafe {
                    *ptr = (*ptr & 0xFFF) | ((value + 0x800) & 0xFFFFF000);
                    *(ptr.offset(1)) = (*(ptr.offset(1)) & 0xFFFFF) | ((value & 0xFFF) << 20);
                })
            }

            R_RISCV_GOT_HI20 => {
                Ok(unsafe {
                    *ptr = (*ptr & 0xFFF) | ((value + 0x800) & 0xFFFFF000)
                })
            }

            // We will not use indirect addressing here
            // So, just put in the direct address instead of the GOT
            // The lower instruction must be changed to addi (typically from lw)
            // to make the value treated as the direct address
            // Hex encoding of addi (opcode/funct3): 0x13/0
            R_RISCV_PCREL_LO12_I => {
                Ok(unsafe {
                    *ptr = (*ptr & 0xF8F80) | 0x13 | ((value & 0xFFF) << 20);
                })
            }

            _ => Err(Error::Parsing("Unsupported relocation"))
        }
    }

    // This is unsafe because it mutates global data (instructions).
    pub unsafe fn rebind(&self, name: &[u8], addr: Elf32_Word) -> Result<(), Error<'a>> {
        for rela in self.jmprel.iter() {
            match ELF32_R_TYPE(rela.r_info) {
                R_RISCV_32 | R_RISCV_JUMP_SLOT => {
                    let sym = self.symtab.get(ELF32_R_SYM(rela.r_info) as usize)
                                         .ok_or("symbol out of bounds of symbol table")?;
                    let sym_name = self.name_starting_at(sym.st_name as usize)?;

                    if sym_name == name {
                        self.update_rela(rela, addr)?
                    }
                }

                R_RISCV_CALL_PLT => {
                    let sym = self.symtab.get(ELF32_R_SYM(rela.r_info) as usize)
                                         .ok_or("symbol out of bounds of symbol table")?;
                    let sym_name = self.name_starting_at(sym.st_name as usize)?;

                    if sym_name == name {
                        self.update_rela(rela, addr - (self.image_off + rela.r_offset))?
                    }
                }

                // No associated symbols for other relocation types.
                _ => ()
            }
        }
        Ok(())
    }

    fn resolve_rela(&self, relas: &[Elf32_Rela], resolve: &dyn Fn(&[u8]) -> Option<Elf32_Word>)
            -> Result<(), Error<'a>> {
        for rela in relas {
            let sym;
            if ELF32_R_SYM(rela.r_info) == 0 {
                sym = None;
            } else {
                sym = Some(self.symtab.get(ELF32_R_SYM(rela.r_info) as usize)
                                    .ok_or("symbol out of bounds of symbol table")?)
            }

            let get_symbol_value = |sym: Option<&Elf32_Sym>| {
                let sym = sym.ok_or("relocation requires an associated symbol")?;
                let sym_name = self.name_starting_at(sym.st_name as usize)?;

                // First, try to resolve against itself.
                match self.lookup(sym_name) {
                    Some(addr) => Ok(addr),
                    None => {
                        // Second, call the user-provided function.
                        match resolve(sym_name) {
                            Some(addr) => Ok(addr),
                            None => {
                                // We couldn't find it anywhere.
                                return Err(Error::Lookup(sym_name))
                            }
                        }
                    }
                }
            };

            let value = match ELF32_R_TYPE(rela.r_info) {
                R_RISCV_NONE =>
                    return Ok(()),

                R_RISCV_RELATIVE =>
                    self.image_off + rela.r_addend as Elf32_Word,

                R_RISCV_32 | R_RISCV_JUMP_SLOT => {
                    get_symbol_value(sym)?
                }

                R_RISCV_CALL_PLT | R_RISCV_GOT_HI20 => {
                    let reloc_value = get_symbol_value(sym)?;
                    reloc_value + rela.r_addend as Elf32_Word - (self.image_off + rela.r_offset)
                }

                R_RISCV_PCREL_LO12_I => {
                    let hi20_reloc_addr = get_symbol_value(sym)?;
                    let hi20_rela = relas.iter().find(|rela| rela.r_offset == (hi20_reloc_addr - self.image_off))
                        .ok_or("corresponding HI20 relocation not found")?;

                    let hi20_sym = self.symtab.get(ELF32_R_SYM(hi20_rela.r_info) as usize);
                    get_symbol_value(hi20_sym)? - hi20_reloc_addr
                }

                _ => return Err("unsupported relocation type")?
            };

            self.update_rela(rela, value)?;
        }

        Ok(())
    }

    pub fn load(data: &[u8], image: &'a mut [u8], resolve: &dyn Fn(&[u8]) -> Option<Elf32_Word>)
            -> Result<Library<'a>, Error<'a>> {
        #![allow(unused_assignments)]

        let ehdr = read_unaligned::<Elf32_Ehdr>(data, 0)
                                  .map_err(|()| "cannot read ELF header")?;

        const IDENT: [u8; EI_NIDENT] = [
            ELFMAG0,    ELFMAG1,     ELFMAG2,    ELFMAG3,
            ELFCLASS32, ELFDATA2LSB, EV_CURRENT, ELFOSABI_NONE,
            /* ABI version */ 0, /* padding */ 0, 0, 0, 0, 0, 0, 0
        ];

        #[cfg(target_arch = "riscv32")]
        const ARCH: u16 = EM_RISCV;
        #[cfg(not(target_arch = "riscv32"))]
        const ARCH: u16 = EM_NONE;

        #[cfg(all(target_feature = "f", target_feature = "d"))]
        const FLAGS: u32 = EF_RISCV_FLOAT_ABI_DOUBLE;

        #[cfg(not(all(target_feature = "f", target_feature = "d")))]
        const FLAGS: u32 = EF_RISCV_FLOAT_ABI_SOFT;

        if ehdr.e_ident != IDENT || ehdr.e_type != ET_DYN || ehdr.e_machine != ARCH || ehdr.e_flags != FLAGS {
            return Err("not a shared library for current architecture")?
        }

        let mut dyn_off = None;
        for i in 0..ehdr.e_phnum {
            let phdr_off = ehdr.e_phoff as usize + mem::size_of::<Elf32_Phdr>() * i as usize;
            let phdr = read_unaligned::<Elf32_Phdr>(data, phdr_off)
                                      .map_err(|()| "cannot read program header")?;

            match phdr.p_type {
                PT_LOAD => {
                    if (phdr.p_vaddr + phdr.p_filesz) as usize > image.len() ||
                            (phdr.p_offset + phdr.p_filesz) as usize > data.len() {
                        return Err("program header requests an out of bounds load")?
                    }
                    let dst = image.get_mut(phdr.p_vaddr as usize..
                                            (phdr.p_vaddr + phdr.p_filesz) as usize)
                                   .ok_or("cannot write to program header destination")?;
                    let src = data.get(phdr.p_offset as usize..
                                       (phdr.p_offset + phdr.p_filesz) as usize)
                                  .ok_or("cannot read from program header source")?;
                    dst.copy_from_slice(src);
                }

                PT_DYNAMIC =>
                    dyn_off = Some(phdr.p_vaddr),

                _ => ()
            }
        }

        let (mut strtab_off, mut strtab_sz) = (0, 0);
        let (mut symtab_off, mut symtab_sz) = (0, 0);
        let (mut rela_off,   mut rela_sz)   = (0, 0);
        let (mut pltrel_off, mut pltrel_sz) = (0, 0);
        let (mut hash_off,   mut hash_sz)   = (0, 0);
        let mut sym_ent  = 0;
        let mut rela_ent = 0;
        let mut nbucket  = 0;
        let mut nchain   = 0;

        let dyn_off = dyn_off.ok_or("cannot find a dynamic header")?;
        for i in 0.. {
            let dyn_off = dyn_off as usize + i * mem::size_of::<Elf32_Dyn>();
            let dyn = get_ref::<Elf32_Dyn>(image, dyn_off)
                              .map_err(|()| "cannot read dynamic header")?;

            let val = unsafe { dyn.d_un.d_val } as usize;
            match dyn.d_tag {
                DT_NULL     => break,
                DT_REL      => return Err("relocations with implicit addend are not supported")?,
                DT_STRTAB   => strtab_off = val,
                DT_STRSZ    => strtab_sz  = val,
                DT_SYMTAB   => symtab_off = val,
                DT_SYMENT   => sym_ent    = val,
                DT_RELA     => rela_off   = val,
                DT_RELASZ   => rela_sz    = val / mem::size_of::<Elf32_Rela>(),
                DT_RELAENT  => rela_ent   = val,
                DT_JMPREL   => pltrel_off = val,
                DT_PLTRELSZ => pltrel_sz  = val / mem::size_of::<Elf32_Rela>(),
                DT_HASH     => {
                    nbucket  = *get_ref::<Elf32_Word>(image, val + 0)
                                        .map_err(|()| "cannot read hash bucket count")? as usize;
                    nchain   = *get_ref::<Elf32_Word>(image, val + 4)
                                        .map_err(|()| "cannot read hash chain count")? as usize;
                    hash_off = val + 8;
                    hash_sz  = nbucket + nchain;
                }
                _ => ()
            }
        }

        if sym_ent != mem::size_of::<Elf32_Sym>() {
            return Err("incorrect symbol entry size")?
        }
        if rela_ent != 0 && rela_ent != mem::size_of::<Elf32_Rela>() {
            return Err("incorrect relocation entry size")?
        }

        // These are the same--there are as many chains as buckets, and the chains only contain
        // the symbols that overflowed the bucket.
        symtab_sz = nchain;

        // Drop the mutability. See also the comment below.
        let image = &*image;

        let strtab = get_ref_slice::<u8>(image, strtab_off, strtab_sz)
                                   .map_err(|()| "cannot read string table")?;
        let symtab = get_ref_slice::<Elf32_Sym>(image, symtab_off, symtab_sz)
                                   .map_err(|()| "cannot read symbol table")?;
        let rela   = get_ref_slice::<Elf32_Rela>(image, rela_off, rela_sz)
                                   .map_err(|()| "cannot read rela entries")?;
        let pltrel = get_ref_slice::<Elf32_Rela>(image, pltrel_off, pltrel_sz)
                                   .map_err(|()| "cannot read pltrel entries")?;
        let hash   = get_ref_slice::<Elf32_Word>(image, hash_off, hash_sz)
                                   .map_err(|()| "cannot read hash entries")?;

        let library = Library {
            image_off:   image.as_ptr() as Elf32_Word,
            image_sz:    image.len(),
            strtab:      strtab,
            symtab:      symtab,
            jmprel:      if pltrel.is_empty() { rela } else { pltrel },
            hash_bucket: &hash[..nbucket],
            hash_chain:  &hash[nbucket..nbucket + nchain],
        };

        // If a borrow exists anywhere, the borrowed memory cannot be mutated except
        // through that pointer or it's UB. However, we need to retain pointers
        // to the symbol tables and relocations, and at the same time mutate the code
        // to resolve the relocations.
        //
        // To avoid invoking UB, we drop the only pointer to the entire area (which is
        // unique since it's a &mut); we retain pointers to the various tables, but
        // we never write to the memory they refer to, so it's safe.
        mem::drop(image);

        library.resolve_rela(rela, resolve)?;
        library.resolve_rela(pltrel, resolve)?;

        Ok(library)
    }
}
