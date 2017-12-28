INCLUDE generated/output_format.ld
INCLUDE generated/regions.ld
ENTRY(_reset_handler)

/* Assume ORIGIN(main_ram) = 0x40000000. Unfortunately,
 * ld does not allow this expression here.
 */
MEMORY {
    runtime (RWX) : ORIGIN = 0x40000000, LENGTH = 0x400000 /* 4M */
}

SECTIONS
{
    .vectors :
    {
        *(.vectors)
    } > runtime

    .text :
    {
        *(.text .text.*)
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
        *(.rodata .rodata.*)
    } > runtime

    .data :
    {
        *(.data .data.*)
    } > runtime

    .bss ALIGN(4) :
    {
        _fbss = .;
        *(.bss .bss.*)
        _ebss = .;
    } > runtime

    .stack ALIGN(0x1000) :
    {
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
