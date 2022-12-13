#!/usr/bin/env python3

import argparse
import importlib
import struct

from sipyco import common_args

from artiq import __version__ as artiq_version
from artiq.master.databases import DeviceDB


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ RTIO channel name map encoder tool")

    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    common_args.verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                        help="device database file (default: '%(default)s')")
    parser.add_argument("file", metavar="FILE", default=None,
                        help="write the result into the specified file, or read from it to show the map (see `--show`)")
    parser.add_argument("--show", default=False, action="store_true",
                        help="show the channel mapping from the specified file, instead of writing to it")

    return parser


def get_rtio_channels(desc):
    if isinstance(desc, dict) and desc["type"] == "local":
        module = importlib.import_module(desc["module"])
        device_class = getattr(module, desc["class"])
        return getattr(device_class, "get_rtio_channels", lambda **kwargs: [])(**desc.get("arguments", {}))
    return []


def get_channel_map(device_db):
    reversed_map = {}
    for dev_name, device in device_db.items():
        try:
            channels = get_rtio_channels(device)
        except Exception as e:
            raise Exception(f"failed to process the device `{dev_name}`") from e
        for chan, suffix in channels:
            assert chan not in reversed_map
            reversed_map[chan] = dev_name + (" " + suffix if suffix is not None else "")

    return reversed_map


def serialize_device_map(channel_map, outfile):
    outfile.write(struct.pack("<I", len(channel_map)))
    for dev_num, dev_name in channel_map.items():
        dev_name_bytes = dev_name.encode("utf-8")
        outfile.write(struct.pack("<II{}s".format(len(dev_name_bytes)), dev_num, len(dev_name_bytes), dev_name_bytes))


def deserialize_device_map(infile):
    result_map = dict()
    ch_count, = struct.unpack_from("<I", infile.read(4))
    for _ in range(ch_count):
        dev_num, dev_name_len = struct.unpack_from("<II", infile.read(8))
        dev_name = struct.unpack_from("<{}s".format(dev_name_len), infile.read(dev_name_len))[0].decode("utf-8")
        assert dev_num not in result_map
        result_map[dev_num] = dev_name
    return result_map


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    if args.show:
        with open(args.file, "rb") as infile:
            chan_map = deserialize_device_map(infile)
        for chan, device in sorted(chan_map.items(), key=lambda x: x[0]):
            print(f"{chan} -> {device}")
    else:
        ddb = DeviceDB(args.device_db)
        chan_map = get_channel_map(ddb.get_device_db())

        with open(args.file, "wb") as outfile:
            serialize_device_map(chan_map, outfile)


if __name__ == "__main__":
    main()
