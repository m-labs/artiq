INCLUDE generated/output_format.ld
ENTRY(_start)

INCLUDE generated/regions.ld

/* Assume ORIGIN(main_ram) = 0x40000000. Unfortunately,
 * ld does not allow this expression here.
 */
MEMORY {
	runtime : ORIGIN = 0x40000000, LENGTH = 0x400000 /* 4M */
}

/* Kernel memory space start right after the runtime,
 * and ends before the runtime stack.
 * Runtime stack is always at the end of main_ram.
 * This stack is shared with the kernel on UP systems.
 */
PROVIDE(_fstack = 0x40000000 + LENGTH(main_ram) - 4);

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
		_heapstart = .;
	} > runtime
}
