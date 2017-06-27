#!/usr/bin/env python3

import argparse
import sys
import os
import asyncio

from artiq.devices.thorlabs_tcube.driver import Tdc, Tpz, TdcSim, TpzSim
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import *


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-P", "--product", required=True,
                        help="type of the Thorlabs T-Cube device to control: "
                             "tdc001/tpz001")
    parser.add_argument("-d", "--device", default=None,
                        help="serial device. See documentation for how to "
                             "specify a USB Serial Number.")
    parser.add_argument("--simulation", action="store_true",
                        help="Put the driver in simulation mode, even if "
                             "--device is used.")
    simple_network_args(parser, 3255)
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

    product = args.product.lower()
    if args.simulation:
        if product == "tdc001":
            dev = TdcSim()
        elif product == "tpz001":
            dev = TpzSim()
        else:
            print("Invalid product string (-P/--product), "
                  "choose from tdc001 or tpz001")
            sys.exit(1)
    else:
        if product == "tdc001":
            dev = Tdc(args.device)
        elif product == "tpz001":
            dev = Tpz(args.device)
        else:
            print("Invalid product string (-P/--product), "
                  "choose from tdc001 or tpz001")
            sys.exit(1)

    try:
        simple_server_loop({product: dev},
                           bind_address_from_args(args), args.port)
    finally:
        dev.close()

if __name__ == "__main__":
    main()
