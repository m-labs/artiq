INCLUDE generated/output_format.ld
INCLUDE generated/regions.ld
ENTRY(_reset_handler)

/* Assume ORIGIN(main_ram) = 0x40000000. Unfortunately,
 * ld does not allow this expression here.
 */
MEMORY {
    firmware (RWX) : ORIGIN = 0x40000000, LENGTH = 0x4000000 /* 64M */
}

SECTIONS
{
    .vectors :
    {
        *(.vectors)
    } > firmware

    .text :
    {
        *(.text .text.*)
    } > firmware

    .eh_frame :
    {
        __eh_frame_start = .;
        KEEP(*(.eh_frame))
        __eh_frame_end = .;
    } > firmware

    .eh_frame_hdr :
    {
        KEEP(*(.eh_frame_hdr))
    } > firmware

    __eh_frame_hdr_start = SIZEOF(.eh_frame_hdr) > 0 ? ADDR(.eh_frame_hdr) : 0;
    __eh_frame_hdr_end = SIZEOF(.eh_frame_hdr) > 0 ? . : 0;

    .gcc_except_table :
    {
        *(.gcc_except_table)
    } > firmware

    /* https://sourceware.org/bugzilla/show_bug.cgi?id=20475 */
    .got :
    {
        *(.got)
    } > firmware

    .got.plt :
    {
        *(.got.plt)
    } > firmware

    .rodata :
    {
        *(.rodata .rodata.*)
    } > firmware

    .data :
    {
        *(.data .data.*)
    } > firmware

    .bss (NOLOAD) : ALIGN(4)
    {
        _fbss = .;
        *(.sbss .sbss.* .bss .bss.*);
        _ebss = .;
    } > firmware

    .stack (NOLOAD) : ALIGN(0x1000)
    {
        _sstack_guard = .;
        . += 0x1000;
        _estack = .;
        . += 0x10000;
        _fstack = . - 16;
    } > firmware

    .heap (NOLOAD) : ALIGN(16)
    {
        _fheap = .;
        . = ORIGIN(firmware) + LENGTH(firmware);
        _eheap = .;
    } > firmware
}
