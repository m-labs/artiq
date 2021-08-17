SECTIONS {
  .bss ALIGN(4) :
  {
    __bss_start = .;
    *(.sbss .sbss.* .bss .bss.*);
    . = ALIGN(4);
    _end = .;
  }
}