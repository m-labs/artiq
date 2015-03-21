#!/usr/bin/env python3

import argparse

from artiq.devices.pdq2.driver import Pdq2
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, init_logger, simple_network_args


def get_argparser():
    parser = argparse.ArgumentParser(description="PDQ2 controller")
    simple_network_args(parser, 3252)
    parser.add_argument(
        "-d", "--device", default=None,
        help="serial port. Omit for simulation mode.")
    parser.add_argument(
        "--dump", default="pdq2_dump.bin",
        help="file to dump pdq2 data into, for later simulation")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)
    port = None
    if args.device is None:
        port = open(args.dump, "wb")
    dev = Pdq2(url=args.device, dev=port)
    try:
        simple_server_loop({"pdq2": dev}, args.bind, args.port,
                           id_parameters="device=" + str(args.device))
    finally:
        dev.close()


if __name__ == "__main__":
    main()
