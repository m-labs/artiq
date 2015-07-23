#!/usr/bin/env python3

import argparse
import struct


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ flash storage image generator")

    parser.add_argument("output", help="output file")

    parser.add_argument("-s", nargs=2, action="append", default=[],
                        metavar=("KEY", "STRING"),
                        help="add string")
    parser.add_argument("-f", nargs=2, action="append", default=[],
                        metavar=("KEY", "FILENAME"),
                        help="add file contents")

    return parser


def write_record(f, key, value):
    key_size = len(key) + 1
    value_size = len(value)
    record_size = key_size + value_size + 4
    f.write(struct.pack(">l", record_size))
    f.write(key.encode())
    f.write(b"\x00")
    f.write(value)


def write_end_marker(f):
    f.write(b"\xff\xff\xff\xff")


def main():
    args = get_argparser().parse_args()
    with open(args.output, "wb") as fo:
        for key, string in args.s:
            write_record(fo, key, string.encode())
        for key, filename in args.f:
            with open(filename, "rb") as fi:
                write_record(fo, key, fi.read())
        write_end_marker(fo)

if __name__ == "__main__":
    main()
