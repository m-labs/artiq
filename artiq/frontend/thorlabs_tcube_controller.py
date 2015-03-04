#!/usr/bin/env python3

import argparse

from artiq.devices.thorlabs_tcube.driver import Tdc, Tpz, TdcSim, TpzSim
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, init_logger


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--device", required=True,
                        help="type of the Thorlabs T-Cube device to control",
                        choices=["TDC001", "TPZ001", "TDCSim", "TPZSim"])
    parser.add_argument("--bind", default="::1",
                        help="hostname or IP address to bind to")
    parser.add_argument("-p", "--port", default=3255, type=int,
                        help="TCP port to listen to")
    parser.add_argument("-s", "--serial", default="/dev/ttyUSB0",
                        help="serial port: on Windows \"COMx\", on Linux a "
                             "device path (e.g. \"/dev/ttyUSB0\").")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    devname = args.device.lower()

    if devname == "tdc001":
        dev = Tdc(args.serial)
    elif devname == "tpz001":
        dev = Tpz(args.serial)
    elif devname == "tdcsim":
        dev = TdcSim()
    elif devname == "tpzsim":
        dev = TpzSim()
    else:
        raise ValueError("Device can be either TDC001, TPZ001, TDCSim"
                         " or TPZSim")

    simple_server_loop({devname: dev}, args.bind, args.port)

if __name__ == "__main__":
    main()
