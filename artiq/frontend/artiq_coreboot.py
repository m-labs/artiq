#!/usr/bin/env python3

import argparse
import sys
import struct

from artiq.tools import verbosity_args, init_logger
from artiq.master.databases import DeviceDB
from artiq.coredevice.comm_mgmt import CommMgmt


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device boot tool")

    verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                       help="device database file (default: '%(default)s')")

    subparsers = parser.add_subparsers(dest="action")

    p_reboot = subparsers.add_parser("reboot",
                                     help="reboot the currently running firmware")

    p_hotswap = subparsers.add_parser("hotswap",
                                      help="load the specified firmware in RAM")

    p_hotswap.add_argument("image", metavar="IMAGE", type=argparse.FileType("rb"),
                           help="runtime image to be executed")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    core_addr = DeviceDB(args.device_db).get("core")["arguments"]["host"]
    mgmt = CommMgmt(core_addr)
    try:
        if args.action == "reboot":
            mgmt.reboot()
        elif args.action == "hotswap":
            mgmt.hotswap(args.image.read())
        else:
            print("An action needs to be specified.", file=sys.stderr)
            sys.exit(1)
    finally:
        mgmt.close()

if __name__ == "__main__":
    main()
