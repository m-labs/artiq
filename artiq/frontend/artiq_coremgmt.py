#!/usr/bin/env python3

import argparse
import struct

from artiq.tools import verbosity_args, init_logger
from artiq.master.databases import DeviceDB
from artiq.master.worker_db import DeviceManager
from artiq.coredevice.comm_kernel import CommKernel
from artiq.coredevice.comm_mgmt import CommMgmt
from artiq.coredevice.profiler import CallgrindWriter


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device "
                                                 "management tool")

    verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                       help="device database file (default: '%(default)s')")

    tools = parser.add_subparsers(dest="tool")
    tools.required = True

    # logging
    t_log = tools.add_parser("log",
                             help="read logs and change log levels")

    subparsers = t_log.add_subparsers(dest="action")

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

    # configuration
    t_config = tools.add_parser("config",
                                help="read and change core device configuration")

    subparsers = t_config.add_subparsers(dest="action")
    subparsers.required = True

    p_read = subparsers.add_parser("read",
                                   help="read key from core device config")
    p_read.add_argument("key", metavar="KEY", type=str,
                        help="key to be read from core device config")

    p_write = subparsers.add_parser("write",
                                    help="write key-value records to core "
                                         "device config")
    p_write.add_argument("-s", "--string", nargs=2, action="append",
                         default=[], metavar=("KEY", "STRING"), type=str,
                         help="key-value records to be written to core device "
                              "config")
    p_write.add_argument("-f", "--file", nargs=2, action="append",
                         type=str, default=[],
                         metavar=("KEY", "FILENAME"),
                         help="key and file whose content to be written to "
                              "core device config")

    p_delete = subparsers.add_parser("delete",
                                     help="delete key from core device config")
    p_delete.add_argument("key", metavar="KEY", nargs=argparse.REMAINDER,
                          default=[], type=str,
                          help="key to be deleted from core device config")

    subparsers.add_parser("erase", help="fully erase core device config")

    # booting
    t_boot = tools.add_parser("reboot",
                              help="reboot the currently running firmware")

    t_hotswap = tools.add_parser("hotswap",
                                  help="load the specified firmware in RAM")

    t_hotswap.add_argument("image", metavar="IMAGE", type=argparse.FileType("rb"),
                           help="runtime image to be executed")

    # profiling
    t_profile = tools.add_parser("profile",
                                 help="account for communications CPU time")

    subparsers = t_profile.add_subparsers(dest="action")
    subparsers.required = True

    p_start = subparsers.add_parser("start",
                                    help="start profiling")
    p_start.add_argument("--interval", metavar="MICROS", type=int, default=2000,
                         help="sampling interval, in microseconds")
    p_start.add_argument("--hits-size", metavar="ENTRIES", type=int, default=8192,
                         help="hit buffer size")
    p_start.add_argument("--edges-size", metavar="ENTRIES", type=int, default=0,
                         help="edge buffer size (edge profiling not implemented)")

    p_stop = subparsers.add_parser("stop",
                                   help="stop profiling")

    p_save = subparsers.add_parser("save",
                                   help="save profile")
    p_save.add_argument("output", metavar="OUTPUT", type=argparse.FileType("w"),
                        help="file to save profile to, in Callgrind format")
    p_save.add_argument("firmware", metavar="FIRMWARE", type=str,
                        help="path to firmware ELF file")
    p_save.add_argument("--no-compression",
                        dest="compression", default=True, action="store_false",
                        help="disable profile compression")

    # misc debug
    t_debug = tools.add_parser("debug",
                               help="specialized debug functions")

    subparsers = t_debug.add_subparsers(dest="action")
    subparsers.required = True

    p_allocator = subparsers.add_parser("allocator",
                                        help="show heap layout")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    device_mgr = DeviceManager(DeviceDB(args.device_db))
    try:
        core_addr = DeviceDB(args.device_db).get("core")["arguments"]["host"]
        kern = CommKernel(core_addr)
        mgmt = CommMgmt(core_addr)

        kern.check_system_info()

        if args.tool == "log":
            if args.action == "set_level":
                mgmt.set_log_level(args.level)
            if args.action == "set_uart_level":
                mgmt.set_uart_log_level(args.level)
            if args.action == "clear":
                mgmt.clear_log()
            if args.action == None:
                print(mgmt.get_log(), end="")

        if args.tool == "config":
            if args.action == "read":
                value = kern.flash_storage_read(args.key)
                if not value:
                    print("Key {} does not exist".format(args.key))
                else:
                    print(value)
            if args.action == "write":
                for key, value in args.string:
                    kern.flash_storage_write(key, value.encode("utf-8"))
                for key, filename in args.file:
                    with open(filename, "rb") as fi:
                        kern.flash_storage_write(key, fi.read())
            if args.action == "delete":
                for key in args.key:
                    kern.flash_storage_remove(key)
            if args.action == "erase":
                kern.flash_storage_erase()

        if args.tool == "reboot":
            mgmt.reboot()

        if args.tool == "hotswap":
            mgmt.hotswap(args.image.read())

        if args.tool == "profile":
            if args.action == "start":
                mgmt.start_profiler(args.interval, args.hits_size, args.edges_size)
            elif args.action == "stop":
                mgmt.stop_profiler()
            elif args.action == "save":
                hits, edges = mgmt.get_profile()
                writer = CallgrindWriter(args.output, args.firmware,
                                         "or1k-linux", args.compression)
                writer.header()
                for addr, count in hits.items():
                    writer.hit(addr, count)
                for (caller, callee), count in edges.items():
                    writer.edge(caller, callee, count)

        if args.tool == "debug":
            if args.action == "allocator":
                mgmt.debug_allocator()

    finally:
        device_mgr.close_devices()

if __name__ == "__main__":
    main()
