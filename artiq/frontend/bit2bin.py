#!/usr/bin/env python3
# Copyright 2014-2017 Robert Jordens <jordens@gmail.com>
# after
# https://github.com/mfischer/fpgadev-zynq/blob/master/top/python/bit_to_zynq_bin.py

import struct


def flip32(data):
    sl = struct.Struct("<I")
    sb = struct.Struct(">I")
    b = memoryview(data)
    d = bytearray(len(data))
    for offset in range(0, len(data), sl.size):
         sb.pack_into(d, offset, *sl.unpack_from(b, offset))
    return d


def bit2bin(bit, bin, flip=False):
    l, = struct.unpack(">H", bit.read(2))
    if l != 9:
        raise ValueError("Missing <0009> header, not a bit file")
    _ = bit.read(l)  # unknown data
    l, = struct.unpack(">H", bit.read(2))
    if l != 1:
        raise ValueError("Missing <0001> header, not a bit file")

    while True:
        key = bit.read(1).decode()
        if not key:
            break
        if key in "abcd":
            d = bit.read(*struct.unpack(">H", bit.read(2)))
            assert d.endswith(b"\x00")
            d = d[:-1].decode()
            name = {
                    "a": "Design",
                    "b": "Part name",
                    "c": "Date",
                    "d": "Time"
                    }[key]
            print("{}: {}".format(name, d))
        elif key == "e":
            l, = struct.unpack(">I", bit.read(4))
            print("Bitstream payload length: {:#x}".format(l))
            d = bit.read(l)
            if flip:
                d = flip32(d)
            bin.write(d)
        else:
            d = bit.read(*struct.unpack(">H", bit.read(2)))
            print("Unexpected key: {}: {}".format(key, d))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Convert FPGA bit files to raw bin format "
                    "suitable for flashing")
    parser.add_argument("-f", "--flip", dest="flip", action="store_true",
            default=False, help="Flip 32-bit endianess (needed for Zynq)")
    parser.add_argument("bitfile", metavar="BITFILE",
                        help="Input bit file name")
    parser.add_argument("binfile", metavar="BINFILE",
                        help="Output bin file name")
    args = parser.parse_args()

    with open(args.bitfile, "rb") as f, open(args.binfile, "wb") as g:
        bit2bin(f, g, args.flip)
