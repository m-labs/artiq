#!/usr/bin/env python3

import argparse

from artiq.tools import verbosity_args, init_logger
from artiq.master.databases import DeviceDB
from artiq.master.worker_db import DeviceManager


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device "
                                                 "log download tool")
    verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.pyon",
                       help="device database file (default: '%(default)s')")

    subparsers = parser.add_subparsers(dest="action")

    p_set_level = subparsers.add_parser("set_level",
                                        help="set minimum level for messages to be logged")
    p_set_level.add_argument("level", metavar="LEVEL", type=str,
                             help="log level (one of: OFF ERROR WARN INFO DEBUG TRACE)")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)
    device_mgr = DeviceManager(DeviceDB(args.device_db))
    try:
        comm = device_mgr.get("comm")
        comm.check_system_info()
        if args.action == "set_level":
            comm.set_log_level(args.level)
        else:
            print(comm.get_log(), end="")
    finally:
        device_mgr.close_devices()


if __name__ == "__main__":
    main()
