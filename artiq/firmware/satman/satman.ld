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

    .bss ALIGN(4) :
    {
        _fbss = .;
        *(.bss .bss.*)
        . = ALIGN(4);
        _ebss = .;
    } > main_ram

    .stack ALIGN(0x1000) :
    {
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
}
