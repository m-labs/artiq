#!/usr/bin/python3

# Copyright (c) 2014 Joe Britton, Sebastien Bourdeauducq

import argparse
from artiq.protocols.pc_rpc import simple_server_loop
import importlib
import novatech409B
importlib.reload(novatech409B)


# This is main loop for use as an ARTIQ driver.
def define_parser():
    parser = argparse.ArgumentParser(
            description="novatech409B-controller",
            epilog="This is a m-labs.com ARTIQ "
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
    return parser


def _get_args():
    p = define_parser()
    return p.parse_args()


def main():
    args = _get_args()
    simple_server_loop(
        {"novatech409B":
        novatech409B.Novatech409B(comport=args.serial_port,
            debug=args.verbosity, simulate_hw=args.simulate_hw)},
            host=args.bind,
            port=args.port)


if __name__ == "__main__":
    main()
