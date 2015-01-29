#!/usr/bin/python3
# Copyright (c) 2014 Joe Britton, Sebastien Bourdeauducq

import argparse
from artiq.protocols.pc_rpc import simple_server_loop
import importlib
import logging
import novatech409B
importlib.reload(novatech409B)


# This is main loop for use as an ARTIQ driver.
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
    parser.add_argument("--log", type=str, default="WARNING",
                        help="set log level; by verbosity: DEBUG > INFO > WARNING > ERROR > CRITICAL")

    return parser

def main():
    args = get_argparser().parse_args()

    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError("Invalid log level: " + args.log)
    logging.basicConfig(level=numeric_level)

    simple_server_loop(
        {"novatech409B":
        novatech409B.Novatech409B(comport=args.serial_port,
            debug=args.verbosity, simulate_hw=args.simulate_hw)},
            host=args.bind,
            port=args.port)

    logging.debug("this is a debug message")
    logging.info("this is an info message")
    logging.warning("this is a warning message")

if __name__ == "__main__":
    main()
