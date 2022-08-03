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

class Cntn:
    def __init__(self, file_path):
        self.channel_names = {}
        with open(file_path, "r") as f:
            lines = f.readlines()
            if lines.pop(0) == "channel_number  channel_name\n":
                lines = [line.split() for line in lines]
                for element in lines:
                    if len(element) == 2:
                        self.channel_names[element[0]] = element[1]

    def get_channel_name(self, ch_number):
        if str(ch_number) in self.channel_names:
            return self.channel_names[str(ch_number)]
        else:
            return "unknown"

    def get_config_string(self):
        names = [ch_num+":"+ch_name for ch_num, ch_name in self.channel_names.items()]
        return ",".join(names)

def main():
    args = get_argparser().parse_args()

    with open(args.output, "w") as f:
        ddb = DeviceDB(args.device_db).get_device_db()
        print("channel_number  channel_name", file=f)
        for device, value in ddb.items():
            if "arguments" in value:
                if "channel" in value["arguments"]:
                    print("{:<16}{}".format(
                        value["arguments"]["channel"], device), file=f)
        f.close()


if __name__ == "__main__":
    main()
