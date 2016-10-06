INCLUDE generated/output_format.ld
ENTRY(_start)

INCLUDE generated/regions.ld

/* First 4M of main memory are reserved for runtime
 * code/data/heap, then comes kernel memory.
 * First 128K of kernel memory are for support code.
 */
MEMORY {
    ksupport (RWX) : ORIGIN = 0x40400000, LENGTH = 0x20000
}

/* Kernel stack is at the end of main RAM. */
PROVIDE(_fstack = ORIGIN(main_ram) + LENGTH(main_ram) - 4);

/* Force ld to make the ELF header as loadable. */
PHDRS
{
    text     PT_LOAD FILEHDR PHDRS;
    eh_frame PT_GNU_EH_FRAME;
}

SECTIONS
{
    .text :
    {
        _ftext = .;
        *(.text .stub .text.* .gnu.linkonce.t.*)
        _etext = .;
    } :text

    .rodata :
    {
        . = ALIGN(4);
        _frodata = .;
        *(.rodata .rodata.* .gnu.linkonce.r.*)
        *(.rodata1)
        _erodata = .;
    } > ksupport

    .eh_frame :
    {
        *(.eh_frame)
    } :text

    .eh_frame_hdr :
    {
        *(.eh_frame_hdr)
    } :text :eh_frame

    .data :
    {
        . = ALIGN(4);
        _fdata = .;
        *(.data .data.* .gnu.linkonce.d.*)
        *(.data1)
        *(.sdata .sdata.* .gnu.linkonce.s.*)
        _edata = .;
    }

    .bss :
    {
        . = ALIGN(4);
        _fbss = .;
        *(.dynsbss)
        *(.sbss .sbss.* .gnu.linkonce.sb.*)
        *(.scommon)
        *(.dynbss)
        *(.bss .bss.* .gnu.linkonce.b.*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    }
}
