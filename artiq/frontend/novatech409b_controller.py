#!/usr/bin/python3

# Written by Joe Britton, 2015

import argparse
import importlib
import logging

from artiq.devices.novatech409b.driver import Novatech409B
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for the Novatech"
        " 409B 4-channel DDS box")
    simple_network_args(parser, 3254)
    parser.add_argument(
        "-s", "--serial-dev",
        default="/dev/ttyUSB0", type=str,
        help="serial port: on Windows \"COMx\","
        " on Linux a device path (e.g. \"/dev/ttyUSB0\")."
        " Use \"sim\" for simulation mode.")
    verbosity_args(parser)
    return parser

def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dev = Novatech409B(args.serial_dev)
    try:
        simple_server_loop(
            {"novatech409b": dev}, args.bind, args.port)
    finally:
        dev.close()

if __name__ == "__main__":
    main()
