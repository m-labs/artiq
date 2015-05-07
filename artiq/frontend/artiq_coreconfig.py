#!/usr/bin/env python3

import argparse

from artiq.master.worker_db import create_device
from artiq.protocols.file_db import FlatFileDB


def to_bytes(string):
    return bytes(string, encoding="ascii")


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device config "
                                                 "remote access")
    parser.add_argument("-r", "--read", type=to_bytes,
                        help="read key from core device config")
    parser.add_argument("-w", "--write", nargs=2, action="append", default=[],
                        metavar=("KEY", "STRING"), type=to_bytes,
                        help="write key-value records to core device config")
    parser.add_argument("-f", "--write-file", nargs=2, action="append",
                        type=to_bytes, default=[], metavar=("KEY", "FILENAME"),
                        help="write the content of a file into core device "
                             "config")
    parser.add_argument("-e", "--erase", action="store_true",
                        help="erase core device config")
    parser.add_argument("-d", "--delete", action="append", default=[],
                        type=to_bytes,
                        help="delete key from core device config")
    parser.add_argument("--ddb", default="ddb.pyon",
                        help="device database file")
    return parser


def main():
    args = get_argparser().parse_args()
    ddb = FlatFileDB(args.ddb)
    comm = create_device(ddb.request("comm"), None)

    if args.read:
        value = comm.flash_storage_read(args.read)
        if not value:
            print("Key {} does not exist".format(args.read))
        else:
            print(value)
    elif args.erase:
            comm.flash_storage_erase()
    elif args.delete:
        for key in args.delete:
            comm.flash_storage_remove(key)
    else:
        if args.write:
            for key, value in args.write:
                comm.flash_storage_write(key, value)
        if args.write_file:
            for key, filename in args.write_file:
                with open(filename, "rb") as fi:
                    comm.flash_storage_write(key, fi.read())

if __name__ == "__main__":
    main()
