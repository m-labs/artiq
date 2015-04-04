static const struct symbol syscalls[] = {
    {"rpc", (void *)0x40021ab0},
    {"rtio_oe", (void *)0x40021478},
    {"rtio_set", (void *)0x400214d4},
    {"rtio_get_counter", (void *)0x400214a0},
    {"rtio_get", (void *)0x400215ec},
    {"rtio_pileup_count", (void *)0x400216f4},
    {"dds_phase_clear_en", (void *)0x400218a4},
    {"dds_program", (void *)0x40021960},
    {NULL, NULL}
};
static const struct symbol eh[] = {
    {"setjmp", (void *)0x40021248},
    {"push", (void *)0x400213c8},
    {"pop", (void *)0x400212c0},
    {"getid", (void *)0x400212e8},
    {"raise", (void *)0x4002139c},
    {NULL, NULL}
};
