#!/usr/bin/env python3

# Written by Joe Britton, 2016

import argparse
import logging
import sys
import asyncio
import os

from artiq.devices.korad_ka3005p.driver import KoradKA3005P
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import *


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for the Korad KA3005P programmable DC power supply")
    simple_network_args(parser, 3256)
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

    if os.name == "nt":
        asyncio.set_event_loop(asyncio.ProactorEventLoop())

    if not args.simulation and args.device is None:
        print("You need to specify either --simulation or -d/--device "
              "argument. Use --help for more information.")
        sys.exit(1)

    dev = KoradKA3005P(args.device if not args.simulation else None)
    asyncio.get_event_loop().run_until_complete(dev.setup())
    try:
        simple_server_loop(
            {"korad_ka3005p": dev}, bind_address_from_args(args), args.port)
    finally:
        dev.close()

if __name__ == "__main__":
    main()
