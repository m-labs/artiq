#!/usr/bin/env python3

import argparse

from sipyco import common_args

from artiq import __version__ as artiq_version
from artiq.master.databases import DeviceDB
from artiq.coredevice.comm_mgmt import CommMgmt


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ device management tool")

    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    common_args.verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                        help="device database file (default: '%(default)s')")
    parser.add_argument("-D", "--device", default=None,
                        help="use specified core device address instead of "
                             "reading device database")
    parser.add_argument("-n", "--dry-run",
                        default=False, action="store_true",
                        help="only show the map and serialized bytes to be sent")

    action = parser.add_subparsers(dest="action")
    action.required = True

    # device
    t_device = action.add_parser("update",
                                 help="update channel->device map on the core device")

    return parser


def serialize_device_map(channel_map):
    dev_len = len(channel_map)
    buffer = bytes()
    buffer += dev_len.to_bytes(4, 'little', signed=False)
    for dev_num, dev_name in channel_map.items():
        buffer += len(dev_name).to_bytes(1, "little", signed=False)
        buffer += dev_num.to_bytes(4, "little", signed=True)
        buffer += bytes(dev_name, "utf-8")

    return buffer


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    if args.device is None:
        ddb = DeviceDB(args.device_db)
        core_addr = ddb.get("core", resolve_alias=True)["arguments"]["host"]
    else:
        core_addr = args.device
    mgmt = CommMgmt(core_addr)

    if args.action == "update":
        dev_db_map = DeviceDB(args.device_db).get_channel_map()
        serialized = serialize_device_map(dev_db_map)
        if args.dry_run:
            print(dev_db_map)
            print(list(map(int, serialized)))
        else:
            mgmt.config_write("device_map", serialized)


if __name__ == "__main__":
    main()
