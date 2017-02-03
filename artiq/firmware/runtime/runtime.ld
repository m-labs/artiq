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

    /DISCARD/ :
    {
        *(.eh_frame)
        *(.gcc_except_table)
    }
}
