INCLUDE generated/output_format.ld
STARTUP(crt0-or1k.o)
ENTRY(_start)

INCLUDE generated/regions.ld

/* First 4M of main memory are reserved for runtime
 * code/data/heap, then comes kernel memory.
 * Next 4M of main memory are reserved for
 * the background RPC queue.
 * First 256K of kernel memory are for support code.
 * Support code is loaded at ORIGIN-0x80 so that ELF headers
 * are also loaded.
 */
MEMORY {
    ksupport (RWX) : ORIGIN = 0x40800000, LENGTH = 0x40000
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

    /* https://sourceware.org/bugzilla/show_bug.cgi?id=20475 */
    .got : {
        _GLOBAL_OFFSET_TABLE_ = .;
        *(.got)
    } :text

    .got.plt : {
        *(.got.plt)
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
        KEEP(*(.eh_frame))
    } :text

    .eh_frame_hdr :
    {
        KEEP(*(.eh_frame_hdr))
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

    /DISCARD/ :
    {
        *(.debug*)
    }
}
