#!/usr/bin/env python3

import argparse
import struct
from artiq.master.databases import DeviceDB
from argparse import RawTextHelpFormatter


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ flash storage image generator",
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("output", help="output file")

    parser.add_argument("-s", nargs=2, action="append", default=[],
                        metavar=("KEY", "STRING"),
                        help="add string")
    parser.add_argument("-f", nargs=2, action="append", default=[],
                        metavar=("KEY", "FILENAME"),
                        help="add file contents")
    parser.add_argument("-e", action="append", default=[],
                        metavar=("ACTION"), choices=["write_ch_names"],
                        help="extended actions:\n"
                        "------------------\n"
                        "write_ch_names\n"
                        "    store channel numbers and corresponding device\n"
                        "    names from device database to core device config\n"
                        "    default path is 'device_db.py', update it with -d")
    parser.add_argument("-d", "--device-db", default="device_db.py",
                        help="path to device database\n"
                        "default: '%(default)s')")

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


def channel_number_to_name(ddb):
    number_to_name = {}
    for device, value in ddb.items():
        if "arguments" in value:
            if "channel" in value["arguments"]:
                number_to_name[value["arguments"]["channel"]] = device
    return number_to_name


def main():
    args = get_argparser().parse_args()
    with open(args.output, "wb") as fo:
        for key, string in args.s:
            write_record(fo, key, string.encode())
        for key, filename in args.f:
            with open(filename, "rb") as fi:
                write_record(fo, key, fi.read())
        for action in args.e:
            if action == "write_ch_names":
                ddb = DeviceDB(args.device_db).get_device_db()
                channel_ntn = channel_number_to_name(ddb)
                if not channel_ntn:
                    print("No device with channel number is found in device database")
                else:
                    channel_database = []
                    print("Write:")
                    for ch_num, ch_name in channel_ntn.items():
                        if "," in ch_name or ":" in ch_name:
                            raise AttributeError(f"channel name cannot contain ',' or ':' in {ch_name}")
                        print(f"channel {ch_num}: {ch_name}")
                        channel_database.append(f"{ch_num}:{ch_name}")
                    channel_database = ",".join(channel_database)
                write_record(fo, "ch_number_to_ch_name", channel_database.encode())
        write_end_marker(fo)

if __name__ == "__main__":
    main()
