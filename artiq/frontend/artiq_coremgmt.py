#!/usr/bin/env python3

import argparse

from sipyco import common_args

from artiq import __version__ as artiq_version
from artiq.master.databases import DeviceDB
from artiq.coredevice.comm_mgmt import CommMgmt
from artiq.coredevice.profiler import CallgrindWriter
from artiq.core_flash import build_dir, artifact_path, convert_gateware


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device "
                                                 "management tool")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    common_args.verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                       help="device database file (default: '%(default)s')")
    parser.add_argument("-D", "--device", default=None,
                        help="use specified core device address instead of "
                             "reading device database")

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

    p_remove = subparsers.add_parser("remove",
                                     help="remove key from core device config")
    p_remove.add_argument("key", metavar="KEY", nargs=argparse.REMAINDER,
                          default=[], type=str,
                          help="key to be removed from core device config")

    subparsers.add_parser("erase", help="fully erase core device config")

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
    p_start.add_argument("--edges-size", metavar="ENTRIES", type=int, default=8192,
                         help="edge buffer size")

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
    p_save.add_argument("--no-demangle",
                        dest="demangle", default=True, action="store_false",
                        help="disable symbol demangling")

    # misc debug
    t_debug = tools.add_parser("debug",
                               help="specialized debug functions")

    subparsers = t_debug.add_subparsers(dest="action")
    subparsers.required = True

    p_allocator = subparsers.add_parser("allocator",
                                        help="show heap layout")

    # flash
    t_flash = tools.add_parser("flash",
                        help="ARTIQ flashing/deployment tool though internet")

    t_flash.add_argument("action", metavar="ACTION", nargs="*",
                        default=[],
                        help="actions to perform, default: gateware/bootloader/firmware/start")
    t_flash.add_argument("-d", "--dir", help="look for board binaries in this directory")
    t_flash.add_argument("-V", "--variant", default=None,
                        help="board variant. Autodetected if only one is installed.")
    t_flash.add_argument("--srcbuild", help="board binaries directory is laid out as a source build tree",
                        default=False, action="store_true")
    t_flash.add_argument("-t", "--target", default="kasli",
                        help="target board, default: %(default)s, one of: "
                             "kasli sayma metlino kc705 phaser")

    return parser


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    if args.device is None:
        ddb = DeviceDB(args.device_db)
        core_addr = ddb.get("core", resolve_alias=True)["arguments"]["host"]
    else:
        core_addr = args.device
    mgmt = CommMgmt(core_addr)

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
            value = mgmt.config_read(args.key)
            if not value:
                print("Key {} does not exist".format(args.key))
            else:
                print(value)
        if args.action == "write":
            for key, value in args.string:
                mgmt.config_write(key, value.encode("utf-8"))
            for key, filename in args.file:
                with open(filename, "rb") as fi:
                    mgmt.config_write(key, fi.read())
        if args.action == "remove":
            for key in args.key:
                mgmt.config_remove(key)
        if args.action == "erase":
            mgmt.config_erase()

    if args.tool == "profile":
        if args.action == "start":
            mgmt.start_profiler(args.interval, args.hits_size, args.edges_size)
        elif args.action == "stop":
            mgmt.stop_profiler()
        elif args.action == "save":
            hits, edges = mgmt.get_profile()
            writer = CallgrindWriter(args.output, args.firmware, "or1k-linux",
                                     args.compression, args.demangle)
            writer.header()
            for addr, count in hits.items():
                writer.hit(addr, count)
            for (caller, callee), count in edges.items():
                writer.edge(caller, callee, count)

    if args.tool == "debug":
        if args.action == "allocator":
            mgmt.debug_allocator()

    if args.tool == "flash":
        (variant, bin_dir, variant_dir, rtm_variant_dir) = build_dir(args)
        if not args.action:
            args.action = "gateware bootloader firmware start".split()
        for action in args.action:
            if action == "gateware":
                gateware_bin = convert_gateware(
                    artifact_path(args, bin_dir, variant_dir, "gateware", "top.bit"))
                with open(gateware_bin, "rb") as fi:
                    file = fi.read()
                    mgmt.flash_write(action, file)
            elif action == "bootloader":
                bootloader_bin = artifact_path(args, bin_dir, variant_dir, "software", "bootloader", "bootloader.bin")
                with open(bootloader_bin, "rb") as fi:
                    file = fi.read()
                    mgmt.flash_write(action, file)
            elif action == "firmware":
                firmware = "runtime"
                firmware_fbi = artifact_path(args, bin_dir,
                    variant_dir, "software", firmware, firmware + ".fbi")
                with open(firmware_fbi, "rb") as fi:
                    file = fi.read()
                    mgmt.flash_write(action, file)
            elif action == "start":
                print('Reloading')
                if mgmt.reload():
                    mgmt.close()

if __name__ == "__main__":
    main()
