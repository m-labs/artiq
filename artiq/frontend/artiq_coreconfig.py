#!/usr/bin/env python3

import argparse

from artiq.master.worker_db import DeviceManager
from artiq.protocols.file_db import FlatFileDB


def to_bytes(string):
    return bytes(string, encoding="ascii")


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device config "
                                                 "remote access")
    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True
    p_read = subparsers.add_parser("read",
                                   help="read key from core device config")
    p_read.add_argument("key", type=to_bytes,
                        help="key to be read from core device config")
    p_write = subparsers.add_parser("write",
                                    help="write key-value records to core "
                                         "device config")
    p_write.add_argument("-s", "--string", nargs=2, action="append",
                         default=[], metavar=("KEY", "STRING"), type=to_bytes,
                         help="key-value records to be written to core device "
                              "config")
    p_write.add_argument("-f", "--file", nargs=2, action="append",
                         type=to_bytes, default=[],
                         metavar=("KEY", "FILENAME"),
                         help="key and file whose content to be written to "
                              "core device config")
    subparsers.add_parser("erase", help="erase core device config")
    p_delete = subparsers.add_parser("delete",
                                     help="delete key from core device config")
    p_delete.add_argument("key", nargs=argparse.REMAINDER,
                          default=[], type=to_bytes,
                          help="key to be deleted from core device config")
    parser.add_argument("--ddb", default="ddb.pyon",
                        help="device database file")
    return parser


def main():
    args = get_argparser().parse_args()
    dmgr = DeviceManager(FlatFileDB(args.ddb))
    try:
        comm = dmgr.get("comm")

        if args.action == "read":
            value = comm.flash_storage_read(args.key)
            if not value:
                print("Key {} does not exist".format(args.key))
            else:
                print(value)
        elif args.action == "erase":
                comm.flash_storage_erase()
        elif args.action == "delete":
            for key in args.key:
                comm.flash_storage_remove(key)
        elif args.action == "write":
            for key, value in args.string:
                comm.flash_storage_write(key, value)
            for key, filename in args.file:
                with open(filename, "rb") as fi:
                    comm.flash_storage_write(key, fi.read())
    finally:
        dmgr.close_devices()

if __name__ == "__main__":
    main()
