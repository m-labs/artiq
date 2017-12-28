INCLUDE generated/output_format.ld
INCLUDE generated/regions.ld
ENTRY(_reset_handler)

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
_fstack = ORIGIN(main_ram) + LENGTH(main_ram) - 4;

/* Force ld to make the ELF header as loadable. */
PHDRS
{
    text     PT_LOAD FILEHDR PHDRS;
    eh_frame PT_GNU_EH_FRAME;
}

SECTIONS
{
    .vectors : {
        *(.vectors)
    } :text

    .text :
    {
        *(.text .text.*)
    } :text

    /* https://sourceware.org/bugzilla/show_bug.cgi?id=20475 */
    .got : {
        PROVIDE(_GLOBAL_OFFSET_TABLE_ = .);
        *(.got)
    } :text

    .got.plt : {
        *(.got.plt)
    } :text

    .rodata :
    {
        *(.rodata .rodata.*)
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
        *(.data .data.*)
    }

    .bss :
    {
        _fbss = .;
        *(.bss .bss.*)
        . = ALIGN(4);
        _ebss = .;
    }

    /DISCARD/ :
    {
        *(.debug*)
    }
}
