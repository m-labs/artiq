#!/usr/bin/env python3

import argparse

from artiq.devices.thorlabs_tcube.driver import Tdc, Tpz, TdcSim, TpzSim
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, init_logger


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-P", "--product", required=True,
                        help="type of the Thorlabs T-Cube device to control",
                        choices=["TDC001", "TPZ001"])
    parser.add_argument("--bind", default="::1",
                        help="hostname or IP address to bind to")
    parser.add_argument("-p", "--port", default=3255, type=int,
                        help="TCP port to listen to")
    parser.add_argument("-d", "--device", default=None,
                        help="serial port. Omit for simulation mode.")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    if args.device is None:
        if args.product == "TDC001":
            dev = TdcSim()
        elif args.product == "TPZ001":
            dev = TpzSim()
    else:
        if args.product == "TDC001":
            dev = Tdc(args.device)
        elif args.product == "TPZ001":
            dev = Tpz(args.device)

    try:
        simple_server_loop({args.product.lower(): dev}, args.bind, args.port)
    finally:
        dev.close()

if __name__ == "__main__":
    main()
