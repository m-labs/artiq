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

  .eh_frame :
  {
    *(.eh_frame.*)
  } > rom

  .rodata :
  {
    *(.rodata.*)
    . = ALIGN(4);
    _end = .;
  } > rom

  .crc (NOLOAD) : ALIGN(4)
  {
    _crc = .;
    . += 4;
  } > rom

  .bss (NOLOAD) :
  {
    _fbss = .;
    *(.sbss .sbss.* .bss .bss.*);
    . = ALIGN(4);
    _ebss = .;
  } > sram

  .stack (NOLOAD) : ALIGN(16)
  {
    /* Ensure we have a certain amount of space available for stack. */
    /*. = ORIGIN(sram) + LENGTH(sram) - 0x1a00; */
    . = ORIGIN(sram) + LENGTH(sram) - 16;
    _fstack = .;
  } > sram
}
