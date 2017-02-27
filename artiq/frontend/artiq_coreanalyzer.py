#!/usr/bin/env python3

import argparse
import sys

from artiq.tools import verbosity_args, init_logger
from artiq.master.databases import DeviceDB
from artiq.master.worker_db import DeviceManager
from artiq.coredevice.comm_analyzer import (get_analyzer_dump,
                                            decode_dump, decoded_dump_to_vcd)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device "
                                                 "RTIO analysis tool")

    verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.pyon",
                       help="device database file (default: '%(default)s')")

    parser.add_argument("-r", "--read-dump", type=str, default=None,
                        help="read raw dump file instead of accessing device")
    parser.add_argument("-p", "--print-decoded", default=False, action="store_true",
                        help="print raw decoded messages")
    parser.add_argument("-w", "--write-vcd", type=str, default=None,
                        help="format and write contents to VCD file")
    parser.add_argument("-d", "--write-dump", type=str, default=None,
                        help="write raw dump file")
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    if (not args.print_decoded
            and args.write_vcd is None and args.write_dump is None):
        print("No action selected, use -p, -w and/or -d. See -h for help.")
        sys.exit(1)

    device_mgr = DeviceManager(DeviceDB(args.device_db))
    if args.read_dump:
        with open(args.read_dump, "rb") as f:
            dump = f.read()
    else:
        core_addr = device_mgr.get_desc("comm")["arguments"]["host"]
        dump = get_analyzer_dump(core_addr)
    decoded_dump = decode_dump(dump)
    if args.print_decoded:
        print("Log channel:", decoded_dump.log_channel)
        print("DDS one-hot:", decoded_dump.dds_onehot_sel)
        for message in decoded_dump.messages:
            print(message)
    if args.write_vcd:
        with open(args.write_vcd, "w") as f:
            decoded_dump_to_vcd(f, device_mgr.get_device_db(),
                                decoded_dump)
    if args.write_dump:
        with open(args.write_dump, "wb") as f:
            f.write(dump)


if __name__ == "__main__":
    main()
