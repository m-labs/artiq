#!/usr/bin/env python3

import argparse
import importlib

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
                        help="write the result into the specified file")

    return parser


def get_rtio_channels(desc):
    if desc["type"] == "local":
        module = importlib.import_module(desc["module"])
        device_class = getattr(module, desc["class"])
        return device_class.get_rtio_channels(**desc.get("arguments", {}))
    return []


def get_channel_map(device_db):
    reversed_map = {}
    for dev_name, device in device_db.items():
        channels = get_rtio_channels(device)
        for chan, suffix in channels:
            reversed_map[chan] = dev_name + (suffix if suffix else "")

    return reversed_map


def serialize_device_map(channel_map):
    dev_len = len(channel_map)
    buffer = bytes()
    buffer += dev_len.to_bytes(4, 'little', signed=False)
    for dev_num, dev_name in channel_map.items():
        buffer += len(dev_name).to_bytes(1, "little", signed=False)
        buffer += dev_num.to_bytes(4, "little", signed=True)
        buffer += bytes(dev_name, "utf-8")

    return buffer


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    ddb = DeviceDB(args.device_db)
    chan_map = get_channel_map(ddb.get_device_db())
    serialized = serialize_device_map(chan_map)

    with open(args.file, "wb") as outfile:
        outfile.write(serialized)
        outfile.flush()


if __name__ == "__main__":
    main()
