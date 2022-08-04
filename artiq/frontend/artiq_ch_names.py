#!/usr/bin/env python3
import argparse
from artiq.master.databases import DeviceDB


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ channel names file"
                                     "template generator")
    parser.add_argument("-d", "--device-db", default="device_db.py",
                        help="device database file (default: '%(default)s')")
    parser.add_argument("-o", "--output", default="channel_ntn.txt",
                        help="output file (default: '%(default)s')")

    return parser


def main():
    args = get_argparser().parse_args()
    channel_names = []
    ddb = DeviceDB(args.device_db).get_device_db()
    for device, value in ddb.items():
        if "arguments" in value:
            if "channel" in value["arguments"]:
                channel_names.append(":".join([
                    str(value["arguments"]["channel"]),
                    device
                ]))
    with open(args.output, "w") as f:
        print(",".join(channel_names), file=f)


if __name__ == "__main__":
    main()
