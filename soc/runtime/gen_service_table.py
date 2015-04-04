#!/usr/bin/env python3

import sys


services = [
    ("syscalls", [
        ("rpc", "comm_rpc"),
        ("rtio_oe", "rtio_oe"),
        ("rtio_set", "rtio_set"),
        ("rtio_get_counter", "rtio_get_counter"),
        ("rtio_get", "rtio_get"),
        ("rtio_pileup_count", "rtio_pileup_count"),
        ("dds_phase_clear_en", "dds_phase_clear_en"),
        ("dds_program", "dds_program"),
    ]),
    ("eh", [
        ("setjmp", "exception_setjmp"),
        ("push", "exception_push"),
        ("pop", "exception_pop"),
        ("getid", "exception_getid"),
        ("raise", "exception_raise"),
    ])
]


def print_uniprocessor():
    for name, contents in services:
        print("static const struct symbol {}[] = {{".format(name))
        for name, value in contents:
            print("    {{\"{}\", {}}},".format(name, value))
        print("    {NULL, NULL}")
        print("};")


def print_biprocessor(ksupport_elf_filename):
    from elftools.elf.elffile import ELFFile
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
    if len(sys.argv) == 1:
        print_uniprocessor()
    elif len(sys.argv) == 2:
        print_biprocessor(sys.argv[1])
    else:
        print("Incorrect number of command line arguments")
        sys.exit(1)

if __name__ == "__main__":
    main()
