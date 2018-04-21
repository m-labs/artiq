#!/usr/bin/env python3

import argparse
import sys
import struct

from artiq.tools import verbosity_args, init_logger
from artiq.master.databases import DeviceDB
from artiq.coredevice.comm_mgmt import CommMgmt


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device debug tool")

    verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                       help="device database file (default: '%(default)s')")

    subparsers = parser.add_subparsers(dest="action")

    p_allocator = subparsers.add_parser("allocator",
                                        help="show heap layout")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    core_addr = DeviceDB(args.device_db).get("core")["arguments"]["host"]
    mgmt = CommMgmt(core_addr)
    try:
        if args.action == "allocator":
            mgmt.debug_allocator()
        else:
            print("An action needs to be specified.", file=sys.stderr)
            sys.exit(1)
    finally:
        mgmt.close()

if __name__ == "__main__":
    main()
