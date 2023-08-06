use board_misoc::csr;
use core::{ptr, slice};
use mailbox;
use rpc_queue;

use kernel_proto::{KERNELCPU_EXEC_ADDRESS, KERNELCPU_LAST_ADDRESS, KSUPPORT_HEADER_SIZE};

#[cfg(has_kernel_cpu)]
pub unsafe fn start() {
    if csr::kernel_cpu::reset_read() == 0 {
        panic!("attempted to start kernel CPU when it is already running")
    }

    stop();

    extern "C" {
        static _binary____ksupport_ksupport_elf_start: u8;
        static _binary____ksupport_ksupport_elf_end: u8;
    }
    let ksupport_elf_start = &_binary____ksupport_ksupport_elf_start as *const u8;
    let ksupport_elf_end = &_binary____ksupport_ksupport_elf_end as *const u8;
    let ksupport_elf = slice::from_raw_parts(
        ksupport_elf_start,
        ksupport_elf_end as usize - ksupport_elf_start as usize,
    );

    if let Err(msg) = load_image(&ksupport_elf) {
        panic!("failed to load kernel CPU image (ksupport.elf): {}", msg);
    }

    csr::kernel_cpu::reset_write(0);

    rpc_queue::init();
}

#[cfg(not(has_kernel_cpu))]
pub unsafe fn start() {
    unimplemented!("not(has_kernel_cpu)")
}

pub unsafe fn stop() {
    #[cfg(has_kernel_cpu)]
    csr::kernel_cpu::reset_write(1);

    mailbox::acknowledge();
    rpc_queue::init();
}

/// Loads the given image for execution on the kernel CPU.
///
/// The entire image including the headers is copied into memory for later use by libunwind, but
/// placed such that the text section ends up at the right location in memory. Currently, we just
/// hard-code the address range, but at least verify that this matches the ELF program header given
/// in the image (avoids loading the – non-relocatable – code at the wrong address on toolchain/…
/// changes).
unsafe fn load_image(image: &[u8]) -> Result<(), &'static str> {
    use dyld::elf::*;
    use dyld::{is_elf_for_current_arch, read_unaligned};

    let ehdr = read_unaligned::<Elf32_Ehdr>(image, 0).map_err(|()| "could not read ELF header")?;

    // The check assumes the two CPUs share the same architecture. This is just to avoid inscrutable
    // errors; we do not functionally rely on this.
    if !is_elf_for_current_arch(&ehdr, ET_EXEC) {
        return Err("not an executable for kernel CPU architecture");
    }

    // First program header should be the main text/… LOAD (see ksupport.ld).
    let phdr = read_unaligned::<Elf32_Phdr>(image, ehdr.e_phoff as usize)
        .map_err(|()| "could not read program header")?;
    if phdr.p_type != PT_LOAD {
        return Err("unexpected program header type");
    }
    if phdr.p_vaddr + phdr.p_memsz > KERNELCPU_LAST_ADDRESS as u32 {
        // This is a weak sanity check only; we also need to fit in the stack, etc.
        return Err("too large for kernel CPU address range");
    }
    const TARGET_ADDRESS: u32 = (KERNELCPU_EXEC_ADDRESS - KSUPPORT_HEADER_SIZE) as _;
    if phdr.p_vaddr - phdr.p_offset != TARGET_ADDRESS {
        return Err("unexpected load address/offset");
    }

    ptr::copy_nonoverlapping(image.as_ptr(), TARGET_ADDRESS as *mut u8, image.len());
    Ok(())
}

pub fn validate(ptr: usize) -> bool {
    ptr >= KERNELCPU_EXEC_ADDRESS && ptr <= KERNELCPU_LAST_ADDRESS
}
