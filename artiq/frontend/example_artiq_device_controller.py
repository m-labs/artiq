#!/usr/bin/python3
# Copyright (c) 2014 Joe Britton, Sebastien Bourdeauducq

import argparse
from artiq.protocols.pc_rpc import simple_server_loop
import importlib
import logging
import novatech409B
#importlib.reload(novatech409B)


def get_argparser():
    parser = argparse.ArgumentParser(
            description="novatech409B-controller",
            epilog="This is a m-labs.hk ARTIQ "
            "controller for a Novatech model 409B 4-channel DDS box. "
            "The hardware interface is a serial port. ")
    parser.add_argument("--bind", default="::1",
                        help="hostname or IP address to bind to;"
                        "::1 is localhost")
    parser.add_argument("--port", default=3254, type=int,
                        help="TCP port to listen to;"
                        "Novatech default is 3254")
    parser.add_argument("--simulate_hw", action="store_true",
                        help="simulate hardware so ARTIQ can be used"
                        "outside the lab")
    parser.add_argument(
        "--serial_port",
        default="/dev/ttyUSB0", type=str,
        help="serial port: on Windows an integer (e.g. 1),"
        "on Linux a device path (e.g. \"/dev/ttyUSB0\")")
    parser.add_argument("--verbosity", type=int, default=1)
    parser.add_argument("--log", type=int, default=30,
                        help="set log level by verbosity: 50 is CRITICAL, 40 is ERROR, 30 is WARNING, 20 is INFO, 10 is DEBUG")

    # add additional commandline arguments here that might be needed to configure the device
    parser.add_argument("--myvar", type=int, default=0,
                       help="example user-defined parameter")

    return parser

def main():
    """
    primary steps:
    1) Create an instance of the device driver class Example_ARTIQ_Device.
    2) Start driver event loop using simple_server_loop()
    """

    # get command line arguments using the standard python argparser library
    args = get_argparser().parse_args()

    # start event loop
    simple_server_loop(
        {"example_artiq_device":
        artiq.devices.example_artiq_device.Example_ARTIQ_Device(
            logging_level=args.verbosity,
            simulate_hw=args.simulate_hw,
            serial_port=args.port)},
            host=args.bind,
            port=args.port )

if __name__ == "__main__":
    main()