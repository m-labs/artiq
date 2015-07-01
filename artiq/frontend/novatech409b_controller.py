#!/usr/bin/env python3

# Written by Joe Britton, 2015

import argparse
import logging
import sys

from artiq.devices.novatech409b.driver import Novatech409B
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for the Novatech 409B 4-channel DDS box")
    simple_network_args(parser, 3254)
    parser.add_argument(
        "-d", "--device", default=None,
        help="serial port.")
    parser.add_argument(
        "--simulation", action="store_true",
        help="Put the driver in simulation mode, even if --device is used.")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    if not args.simulation and args.device is None:
        print("You need to specify either --simulation or -d/--device "
              "argument. Use --help for more information.")
        sys.exit(1)

    dev = Novatech409B(args.device if not args.simulation else None)
    try:
        simple_server_loop(
            {"novatech409b": dev}, args.bind, args.port)
    finally:
        dev.close()

if __name__ == "__main__":
    main()
