#!/usr/bin/env python3
import argparse
import sys
from artiq.master.databases import DeviceDB


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ channel names "
                                     "configuration in device database")
    parser.add_argument("-d", "--device-db", default="device_db.py",
                        help="device database file (default: '%(default)s')")

    return parser


def main():
    args = get_argparser().parse_args()
    ddb = DeviceDB(args.device_db).get_device_db()

    for device, value in ddb.items():
        if "arguments" in value:
            if "channel" in value["arguments"]:
                print(":".join([str(value["arguments"]["channel"]),
                                device]), file=sys.stdout)

if __name__ == "__main__":
    main()
