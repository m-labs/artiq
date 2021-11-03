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
    } > main_ram

    .eh_frame :
    {
        __eh_frame_start = .;
        KEEP(*(.eh_frame))
        __eh_frame_end = .;
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
}
