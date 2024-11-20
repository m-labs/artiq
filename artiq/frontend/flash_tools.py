import atexit
import os
import tempfile
import struct


def artifact_path(this_binary_dir, *path_filename, srcbuild=False):
    if srcbuild:
        # source tree - use path elements to locate file
        return os.path.join(this_binary_dir, *path_filename)
    else:
        # flat tree - all files in the same directory, discard path elements
        *_, filename = path_filename
        return os.path.join(this_binary_dir, filename)


def fetch_bin(binary_dir, components, srcbuild=False):
    def convert_gateware(bit_filename):
        bin_handle, bin_filename = tempfile.mkstemp(
            prefix="artiq_", suffix="_" + os.path.basename(bit_filename))
        with open(bit_filename, "rb") as bit_file, open(bin_handle, "wb") as bin_file:
            bit2bin(bit_file, bin_file)
        atexit.register(lambda: os.unlink(bin_filename))
        return bin_filename

    if len(components) > 1:
        bins = []
        for option in components:
            try:
                bins.append(fetch_bin(binary_dir, [option], srcbuild))
            except FileNotFoundError:
                pass

        if bins is None:
            raise FileNotFoundError("multiple components not found: {}".format(
                                        " ".join(components)))
        
        if len(bins) > 1:
            raise ValueError("more than one file, "
                             "please clean up your build directory. "
                             "Found files: {}".format(
                             " ".join(bins)))

        return bins[0]

    else:
        component = components[0]
        path = artifact_path(binary_dir, *{
            "gateware": ["gateware", "top.bit"],
            "boot": ["boot.bin"],
            "bootloader": ["software", "bootloader", "bootloader.bin"],
            "runtime": ["software", "runtime", "runtime.fbi"],
            "satman": ["software", "satman", "satman.fbi"],
        }[component], srcbuild=srcbuild)

        if not os.path.exists(path):
            raise FileNotFoundError("{} not found".format(component))

        if component == "gateware":
            path = convert_gateware(path)

        return path


# Copyright 2014-2017 Robert Jordens <jordens@gmail.com>
# after
# https://github.com/mfischer/fpgadev-zynq/blob/master/top/python/bit_to_zynq_bin.py

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
