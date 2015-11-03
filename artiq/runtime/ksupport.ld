INCLUDE generated/output_format.ld
ENTRY(_start)

INCLUDE generated/regions.ld

/* First 4M of main memory are reserved for runtime code/data
 * then comes kernel memory. First 32K of kernel memory are for support code.
 */
MEMORY {
    ksupport : ORIGIN = 0x40400000, LENGTH = 0x8000
}

/* On AMP systems, kernel stack is at the end of main RAM,
 * before the runtime stack. Leave 1M for runtime stack.
 */
PROVIDE(_fstack = 0x40000000 + LENGTH(main_ram) - 1024*1024 - 4);

SECTIONS
{
    .text :
    {
        _ftext = .;
        *(.text .stub .text.* .gnu.linkonce.t.*)
        _etext = .;
    } > ksupport

    .rodata :
    {
        . = ALIGN(4);
        _frodata = .;
        *(.rodata .rodata.* .gnu.linkonce.r.*)
        *(.rodata1)
        _erodata = .;
    } > ksupport

    .data :
    {
        . = ALIGN(4);
        _fdata = .;
        *(.data .data.* .gnu.linkonce.d.*)
        *(.data1)
        *(.sdata .sdata.* .gnu.linkonce.s.*)
        _edata = .;
    } > ksupport

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
        . = ALIGN(8);
        _heapstart = .;
    } > ksupport
}
