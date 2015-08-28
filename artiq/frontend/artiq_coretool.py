#!/usr/bin/env python3

import argparse

from artiq.master.worker_db import DeviceManager
from artiq.protocols.file_db import FlatFileDB


def to_bytes(string):
    return bytes(string, encoding="ascii")


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device "
                                                 "remote access tool")
    parser.add_argument("-d", "--ddb", default="ddb.pyon",
                        help="device database file")

    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True

    # Log Read command
    subparsers.add_parser("log",
                          help="read from the core device log ring buffer")

    # Configuration Read command
    p_read = subparsers.add_parser("cfg-read",
                                   help="read key from core device config")
    p_read.add_argument("key", type=str,
                        help="key to be read from core device config")

    # Configuration Write command
    p_write = subparsers.add_parser("cfg-write",
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

    # Configuration Delete command
    p_delete = subparsers.add_parser("cfg-delete",
                                     help="delete key from core device config")
    p_delete.add_argument("key", nargs=argparse.REMAINDER,
                          default=[], type=str,
                          help="key to be deleted from core device config")

    # Configuration Erase command
    subparsers.add_parser("cfg-erase", help="erase core device config")

    return parser


def main():
    args = get_argparser().parse_args()
    dmgr = DeviceManager(FlatFileDB(args.ddb))
    try:
        comm = dmgr.get("comm")
        comm.check_ident()

        if args.action == "log":
          print(comm.get_log())
        elif args.action == "cfg-read":
            value = comm.flash_storage_read(args.key)
            if not value:
                print("Key {} does not exist".format(args.key))
            else:
                print(value)
        elif args.action == "cfg-write":
            for key, value in args.string:
                comm.flash_storage_write(key, value.encode("utf-8"))
            for key, filename in args.file:
                with open(filename, "rb") as fi:
                    comm.flash_storage_write(key, fi.read())
        elif args.action == "cfg-delete":
            for key in args.key:
                comm.flash_storage_remove(key)
        elif args.action == "cfg-erase":
                comm.flash_storage_erase()
    finally:
        dmgr.close_devices()

if __name__ == "__main__":
    main()
