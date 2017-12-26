INCLUDE generated/output_format.ld
STARTUP(crt0-or1k.o)
ENTRY(_start)

INCLUDE generated/regions.ld

/* Assume ORIGIN(main_ram) = 0x40000000. Unfortunately,
 * ld does not allow this expression here.
 */
MEMORY {
    runtime (RWX) : ORIGIN = 0x40000000, LENGTH = 0x400000 /* 4M */
}

SECTIONS
{
    .text :
    {
        _ftext = .;
        *(.text .stub .text.* .gnu.linkonce.t.*)
        _etext = .;
    } > runtime

    .eh_frame :
    {
        __eh_frame_start = .;
        KEEP(*(.eh_frame))
        __eh_frame_end = .;
    } > runtime

    .eh_frame_hdr :
    {
        KEEP(*(.eh_frame_hdr))
    } > runtime

    __eh_frame_hdr_start = SIZEOF(.eh_frame_hdr) > 0 ? ADDR(.eh_frame_hdr) : 0;
    __eh_frame_hdr_end = SIZEOF(.eh_frame_hdr) > 0 ? . : 0;

    /* https://sourceware.org/bugzilla/show_bug.cgi?id=20475 */
    .got :
    {
        _GLOBAL_OFFSET_TABLE_ = .;
        *(.got)
    } > runtime

    .got.plt :
    {
        *(.got.plt)
    } > runtime

    .rodata :
    {
        . = ALIGN(4);
        _frodata = .;
        *(.rodata .rodata.* .gnu.linkonce.r.*)
        *(.rodata1)
        _erodata = .;
    } > runtime

    .data :
    {
        . = ALIGN(4);
        _fdata = .;
        *(.data .data.* .gnu.linkonce.d.*)
        *(.data1)
        *(.sdata .sdata.* .gnu.linkonce.s.*)
        _edata = .;
    } > runtime

    .storage :
    {
        /* Keep in sync with artiq_flash.py */
        .  = _ftext + 0x100000;
        _fstorage = .;
        . += /*SPIFLASH_SECTOR_SIZE*/ 0x10000;
        _estorage = .;
    } > runtime

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
    } > runtime

    .stack :
    {
        . = ALIGN(0x1000);
        _estack = .;
        . += 0x4000;
        _fstack = . - 4;
    } > runtime

    .heap :
    {
        _fheap = .;
        . = ORIGIN(runtime) + LENGTH(runtime);
        _eheap = .;
    } > runtime
}
