#!/usr/bin/env python3.5
# Copyright 2014-2015 Robert Jordens <jordens@gmail.com>
# after
# https://github.com/mfischer/fpgadev-zynq/blob/master/top/python/bit_to_zynq_bin.py
#
# This file is part of redpid.
#
# redpid is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# redpid is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with redpid.  If not, see <http://www.gnu.org/licenses/>.

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
    bitfile = open(bit, "rb")

    l, = struct.unpack(">H", bitfile.read(2))
    if l != 9:
        raise ValueError("Missing <0009> header, not a bit file")

    bitfile.read(l)
    d = bitfile.read(*struct.unpack(">H", bitfile.read(2)))
    if d != b"a":
        raise ValueError("Missing <a> header, not a bit file")

    d = bitfile.read(*struct.unpack(">H", bitfile.read(2)))
    print("Design name:", d)

    while True:
        key = bitfile.read(1)
        if not key:
            break
        if key in b"bcd":
            d = bitfile.read(*struct.unpack(">H", bitfile.read(2)))
            name = {b"b": "Partname", b"c": "Date", b"d": "Time"}[key]
            print(name, d)
        elif key == b"e":
            l, = struct.unpack(">I", bitfile.read(4))
            print("found binary data length:", l)
            d = bitfile.read(l)
            if flip:
                d = flip32(d)
            open(bin, "wb").write(d)
        else:
            d = bitfile.read(*struct.unpack(">H", bitfile.read(2)))
            print("Unexpected key: ", key, d)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
            description="Convert FPGA bit files to raw bin format suitable for flashing")
    parser.add_argument("-f", "--flip", dest="flip", action="store_true",
            default=False, help="Flip 32-bit endianess (needed for Zynq)")
    parser.add_argument("bitfile", help="Input bit file name")
    parser.add_argument("binfile", help="Output bin file name")
    args = parser.parse_args()

    bit2bin(args.bitfile, args.binfile, args.flip)
