#!/usr/bin/python3
# Copyright (c) 2014 Joe Britton, Sebastien Bourdeauducq

import argparse
from artiq.protocols.pc_rpc import simple_server_loop
import importlib
import logging

from artiq.tools import verbosity_args, init_logger

import artiq.devices.ExampleARTIQDevice
importlib.reload(artiq.devices.ExampleARTIQDevice)


def get_argparser():
    parser = argparse.ArgumentParser(
            description="example_artiq_device_controller",
            epilog="This is a sample m-labs.hk ARTIQ "
            "device controller.")
    parser.add_argument("--bind", default="::1",
                        help="hostname or IP address to bind to;"
                        "::1 is localhost")
    parser.add_argument("--port", default=3254, type=int,
                        help="TCP port to listen to")
    parser.add_argument("--simulate_hw", action="store_true",
                        help="simulate hardware so ARTIQ can be used"
                        "outside the lab")
    parser.add_argument(
        "--serial_port",
        default="/dev/ttyUSB0", type=str,
        help="serial port: on Windows an integer (e.g. 1),"
        "on Linux a device path (e.g. \"/dev/ttyUSB0\")")

    # add additional commandline arguments here that might be needed to configure the device
    parser.add_argument("--myvar", type=int, default=0,
                       help="example user-defined parameter")
    verbosity_args(parser)
    return parser

def main():
    """
    primary steps:
    1) Create an instance of the device driver class Example_ARTIQ_Device.
    2) Start driver event loop using simple_server_loop()
    """

    # get command line arguments using the standard python argparser library
    args = get_argparser().parse_args()
    log_fmt = "%(asctime)-15s [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
    init_logger(args, format=log_fmt)

    # start event loop
    simple_server_loop(
        {"example_artiq_device":
        artiq.devices.example_artiq_device.ExampleARTIQDevice(
            simulate_hw=args.simulate_hw,
            serial_port=args.port)},
            host=args.bind,
            port=args.port )

if __name__ == "__main__":
    main()