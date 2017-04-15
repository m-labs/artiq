#!/usr/bin/env python3

import argparse

from artiq.tools import verbosity_args, init_logger
from artiq.master.databases import DeviceDB
from artiq.master.worker_db import DeviceManager
from artiq.coredevice.comm_mgmt import CommMgmt


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device "
                                                 "log download tool")
    verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.pyon",
                       help="device database file (default: '%(default)s')")

    subparsers = parser.add_subparsers(dest="action")

    p_clear = subparsers.add_parser("clear",
                                    help="clear log buffer")

    p_set_level = subparsers.add_parser("set_level",
                                        help="set minimum level for messages to be logged")
    p_set_level.add_argument("level", metavar="LEVEL", type=str,
                             help="log level (one of: OFF ERROR WARN INFO DEBUG TRACE)")

    p_set_uart_level = subparsers.add_parser("set_uart_level",
                                             help="set minimum level for messages to be logged "
                                                  "to UART")
    p_set_uart_level.add_argument("level", metavar="LEVEL", type=str,
                                  help="log level (one of: OFF ERROR WARN INFO DEBUG TRACE)")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)
    device_mgr = DeviceManager(DeviceDB(args.device_db))
    try:
        core_addr = device_mgr.get_desc("comm")["arguments"]["host"]
        mgmt = CommMgmt(device_mgr, core_addr)
        if args.action == "set_level":
            mgmt.set_log_level(args.level)
        elif args.action == "set_uart_level":
            mgmt.set_uart_log_level(args.level)
        elif args.action == "clear":
            mgmt.clear_log()
        else:
            print(mgmt.get_log(), end="")
    finally:
        device_mgr.close_devices()


if __name__ == "__main__":
    main()
