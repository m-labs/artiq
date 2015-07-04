#!/usr/bin/env python3

import sys

from elftools.elf.elffile import ELFFile


services = [
    ("syscalls", [
        ("now_init", "now_init"),
        ("now_save", "now_save"),

        ("watchdog_set", "watchdog_set"),
        ("watchdog_clear", "watchdog_clear"),

        ("rpc", "rpc"),

        ("rtio_get_counter", "rtio_get_counter"),

        ("ttl_set_o", "ttl_set_o"),
        ("ttl_set_oe", "ttl_set_oe"),
        ("ttl_set_sensitivity", "ttl_set_sensitivity"),
        ("ttl_get", "ttl_get"),
        ("ttl_clock_set", "ttl_clock_set"),

        ("dds_init", "dds_init"),
        ("dds_batch_enter", "dds_batch_enter"),
        ("dds_batch_exit", "dds_batch_exit"),
        ("dds_set", "dds_set"),
    ]),

    ("eh", [
        ("setjmp", "exception_setjmp"),
        ("push", "exception_push"),
        ("pop", "exception_pop"),
        ("getid", "exception_getid"),
        ("raise", "exception_raise"),
    ])
]


def print_service_table(ksupport_elf_filename):
    with open(ksupport_elf_filename, "rb") as f:
        elf = ELFFile(f)
        symtab = elf.get_section_by_name(b".symtab")
        symbols = {symbol.name: symbol.entry.st_value
                   for symbol in symtab.iter_symbols()}
    for name, contents in services:
        print("static const struct symbol {}[] = {{".format(name))
        for name, value in contents:
            print("    {{\"{}\", (void *)0x{:08x}}},"
                  .format(name, symbols[bytes(value, "ascii")]))
        print("    {NULL, NULL}")
        print("};")


def main():
    if len(sys.argv) == 2:
        print_service_table(sys.argv[1])
    else:
        print("Incorrect number of command line arguments")
        sys.exit(1)

if __name__ == "__main__":
    main()
