INCLUDE generated/output_format.ld
INCLUDE generated/regions.ld
ENTRY(_reset_handler)

SECTIONS
{
  .vectors :
  {
    _begin = .;
    *(.vectors)
  } > rom

  .text :
  {
    *(.text .text.*)
  } > rom

  .rodata :
  {
    *(.rodata.*)
    . = ALIGN(4);
    _end = .;
  } > rom

  .crc ALIGN(4) :
  {
    _crc = .;
    . += 4;
  }

  .bss :
  {
    _fbss = .;
    *(.bss .bss.*)
    . = ALIGN(4);
    _ebss = .;
  } > sram

  .stack :
  {
    /* Ensure we have a certain amount of space available for stack. */
    . = ORIGIN(sram) + LENGTH(sram) - 0x800;
    . = ORIGIN(sram) + LENGTH(sram) - 4;
    _fstack = .;
  } > sram
}
