INCLUDE generated/output_format.ld
INCLUDE generated/regions.ld
ENTRY(_reset_handler)

SECTIONS
{
    .vectors :
    {
        *(.vectors)
    } > main_ram

    .text :
    {
        *(.text .text.*)
        . = ALIGN(0x40000);
    } > main_ram

    .eh_frame :
    {
        __eh_frame_start = .;
        KEEP(*(.eh_frame))
        __eh_frame_end = .;
    } > main_ram

    .eh_frame_hdr :
    {
        KEEP(*(.eh_frame_hdr))
    } > main_ram

    __eh_frame_hdr_start = SIZEOF(.eh_frame_hdr) > 0 ? ADDR(.eh_frame_hdr) : 0;
    __eh_frame_hdr_end = SIZEOF(.eh_frame_hdr) > 0 ? . : 0;

    .gcc_except_table :
    {
        *(.gcc_except_table)
    } > main_ram

    /* https://sourceware.org/bugzilla/show_bug.cgi?id=20475 */
    .got :
    {
        PROVIDE(_GLOBAL_OFFSET_TABLE_ = .);
        *(.got)
    } > main_ram

    .got.plt :
    {
        *(.got.plt)
    } > main_ram

    .rodata :
    {
        _frodata = .;
        *(.rodata .rodata.*)
        _erodata = .;
    } > main_ram

    .data :
    {
        *(.data .data.*)
    } > main_ram

    .sdata :
    {
        *(.sdata .sdata.*)
    } > main_ram

    .bss (NOLOAD) : ALIGN(4)
    {
        _fbss = .;
        *(.sbss .sbss.* .bss .bss.*);
        . = ALIGN(4);
        _ebss = .;
    } > main_ram

    .stack (NOLOAD) : ALIGN(0x1000)
    {
        _sstack_guard = .;
        . += 0x1000;
        _estack = .;
        . += 0x10000;
        _fstack = . - 16;
    } > main_ram

    /* remainder of 64MB for heap for alloc use */
    .heap (NOLOAD) : ALIGN(16)
    {
        _fheap = .;
        . = 0x44000000; // not to overwrite RPC queue
        _eheap = .;
    } > main_ram
}
