/* Force ld to make the ELF header as loadable. */
PHDRS
{
    headers     PT_LOAD FILEHDR PHDRS ;
    text        PT_LOAD ;
    data        PT_LOAD ;
    dynamic     PT_DYNAMIC ;
    eh_frame    PT_GNU_EH_FRAME ;
}

SECTIONS
{
    /* Push back .text section enough so that ld.lld not complain */
    . = SIZEOF_HEADERS;

    .text :
    {
        *(.text .text.*)
    } : text

    .rodata :
    {
        *(.rodata .rodata.*)
    }

    .eh_frame :
    {
        KEEP(*(.eh_frame))
    } : text

    .eh_frame_hdr :
    {
        KEEP(*(.eh_frame_hdr))
    } : text : eh_frame

    .data :
    {
        *(.data)
    } : data

    .dynamic :
    {
        *(.dynamic)
    } : data : dynamic

    .bss (NOLOAD) : ALIGN(4)
    {
        __bss_start = .;
        *(.sbss .sbss.* .bss .bss.*);
        . = ALIGN(4);
        _end = .;
    }

    . = ALIGN(0x1000);
    _sstack_guard = .;
}
