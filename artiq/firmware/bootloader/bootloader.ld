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

  /*
   * The compiler_builtins crate includes some GOTPC relocations, which require a GOT symbol,
   * but don't actually need a GOT. This really ought to be fixed on rustc level, but I'm afraid
   * it will add further complications to our build system that aren't pulling their weight.
   */
  _GLOBAL_OFFSET_TABLE_ = .;

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
    /*. = ORIGIN(sram) + LENGTH(sram) - 0x1a00; */
    . = ORIGIN(sram) + LENGTH(sram) - 4;
    _fstack = .;
  } > sram
}
