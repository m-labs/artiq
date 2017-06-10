#!/usr/bin/env python3

import argparse
import sys
import time

from artiq.devices.pdq.driver import PDQ
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import *


def get_argparser():
    parser = argparse.ArgumentParser(description="""PDQ controller.

    Use this controller for PDQ stacks that are connected via USB.""")
    simple_network_args(parser, 3252)
    parser.add_argument("-d", "--device", default=None, help="serial port")
    parser.add_argument("--simulation", action="store_true",
                        help="do not open any device but dump data")
    parser.add_argument("--dump", default="pdq_dump.bin",
                        help="file to dump simulation data into")
    parser.add_argument("-r", "--reset", default=False,
                        action="store_true", help="reset device [%(default)s]")
    parser.add_argument("-b", "--boards", default=3, type=int,
                        help="number of boards [%(default)s]")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)
    port = None

    if not args.simulation and args.device is None:
        print("You need to specify either --simulation or -d/--device "
              "argument. Use --help for more information.")
        sys.exit(1)

    if args.simulation:
        port = open(args.dump, "wb")
    dev = PDQ(url=args.device, dev=port, num_boards=args.boards)
    try:
        if args.reset:
            dev.write(b"")  # flush eop
            dev.write_config(reset=True)
            time.sleep(.1)

        dev.write_crc(0)
        dev.checksum = 0

        simple_server_loop({"pdq": dev}, bind_address_from_args(args),
                           args.port, description="device=" + str(args.device))
    finally:
        dev.close()


if __name__ == "__main__":
    main()
