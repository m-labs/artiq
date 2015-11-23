INCLUDE generated/output_format.ld
ENTRY(_start)

INCLUDE generated/regions.ld

/* Assume ORIGIN(main_ram) = 0x40000000. Unfortunately,
 * ld does not allow this expression here.
 */
MEMORY {
	runtime : ORIGIN = 0x40000000, LENGTH = 0x400000 /* 4M */
}

/* First 4M of main memory are reserved for runtime code/data
 * then comes kernel memory. First 32K of kernel memory are for support code.
 */
MEMORY {
  kernel : ORIGIN = 0x40400000, LENGTH = 0x8000
}

/* Kernel memory space start right after the runtime,
 * and ends before the runtime stack.
 * Runtime stack is always at the end of main_ram.
 * This stack is shared with the kernel on UP systems.
 */
PROVIDE(_fstack = 0x40000000 + LENGTH(main_ram) - 4);

/* On AMP systems, kernel stack is at the end of main RAM,
 * before the runtime stack. Leave 1M for runtime stack.
 */
PROVIDE(_kernel_fstack = 0x40000000 + LENGTH(main_ram) - 1024*1024 - 4);

SECTIONS
{
	.text :
	{
		_ftext = .;
		*(.text .stub .text.* .gnu.linkonce.t.*)
		_etext = .;
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
		. = ALIGN(8);
	} > runtime

	/DISCARD/ :
	{
		*(.eh_frame)
	}

	_heapstart = .;
}
