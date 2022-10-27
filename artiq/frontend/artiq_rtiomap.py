#!/usr/bin/env python3

import argparse
import json
from sys import stdout
from os import fdopen

from sipyco import common_args

from artiq import __version__ as artiq_version
from artiq.master.databases import DeviceDB


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ RTIO channel map encoder tool")

    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    common_args.verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                        help="device database file (default: '%(default)s')")
    parser.add_argument("-D", "--device", default=None,
                        help="use specified core device address instead of "
                             "reading device database")
    parser.add_argument("-j", "--json",
                        default=False, action="store_true",
                        help="print the map in JSON format")
    parser.add_argument("-s", "--stdout", default=False, action="store_true",
                        help="print the result into stdout")
    parser.add_argument("-f", "--file", default=None,
                        help="write the result into the specified file")

    return parser


def get_channel_map(device_db):
    reversed_map = {}
    for dev_name, device in device_db.items():
        if dev_name == 'Grabber':
            chan = device["arguments"]["channel_base"]
            reversed_map[chan] = dev_name + " RIO coordinates"
            reversed_map[chan + 1] = dev_name + " RIO mask"
        elif dev_name == 'Phaser':
            chan = device["arguments"]["channel_base"]
            for chan_x in range(chan, chan + 5):
                reversed_map[chan_x] = dev_name
        elif ("arguments" in device
              and "channel" in device["arguments"]
              and device["type"] == "local"
              and device["module"].startswith("artiq.coredevice.")):
            chan = device["arguments"]["channel"]
            reversed_map[chan] = dev_name

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

    if args.file:
        outfile = open(args.file, "wb")
    elif args.stdout:
        outfile = fdopen(stdout.fileno(), "wb", closefd=False)
    else:
        raise Exception("either stdout or file should be chosen")

    if args.json:
        data = bytes(json.dumps(chan_map, indent=2), "utf-8")
    else:
        data = serialized

    outfile.write(data)
    outfile.flush()


if __name__ == "__main__":
    main()
