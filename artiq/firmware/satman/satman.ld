INCLUDE generated/output_format.ld
STARTUP(crt0-or1k.o)
ENTRY(_start)

INCLUDE generated/regions.ld

SECTIONS
{
    .text :
    {
        _ftext = .;
        *(.text .stub .text.* .gnu.linkonce.t.*)
        _etext = .;
    } > main_ram

    /* https://sourceware.org/bugzilla/show_bug.cgi?id=20475 */
    .got :
    {
        _GLOBAL_OFFSET_TABLE_ = .;
        *(.got)
    } > main_ram

    .got.plt :
    {
        *(.got.plt)
    } > main_ram

    .rodata :
    {
        . = ALIGN(4);
        _frodata = .;
        *(.rodata .rodata.* .gnu.linkonce.r.*)
        *(.rodata1)
        _erodata = .;
    } > main_ram

    .data :
    {
        . = ALIGN(4);
        _fdata = .;
        *(.data .data.* .gnu.linkonce.d.*)
        *(.data1)
        *(.sdata .sdata.* .gnu.linkonce.s.*)
        _edata = .;
    } > main_ram

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
    } > main_ram

    .stack :
    {
        . = ALIGN(0x1000);
        _estack = .;
        . += 0x4000;
        _fstack = . - 4;
    } > main_ram

    .heap :
    {
        _fheap = .;
        . = ORIGIN(main_ram) + LENGTH(main_ram);
        _eheap = .;
    } > main_ram

    /DISCARD/ :
    {
        *(.eh_frame)
        *(.gcc_except_table)
    }
}
