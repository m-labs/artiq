#!/usr/bin/env python3

import argparse

from artiq.tools import verbosity_args, init_logger
from artiq.master.databases import DeviceDB
from artiq.coredevice.comm_mgmt import CommMgmt


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device "
                                                 "log tool")
    verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
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

    core_addr = DeviceDB(args.device_db).get("core")["arguments"]["host"]
    mgmt = CommMgmt(core_addr)
    try:
        if args.action == "set_level":
            mgmt.set_log_level(args.level)
        elif args.action == "set_uart_level":
            mgmt.set_uart_log_level(args.level)
        elif args.action == "clear":
            mgmt.clear_log()
        else:
            print(mgmt.get_log(), end="")
    finally:
        mgmt.close()


if __name__ == "__main__":
    main()
