#!/usr/bin/env python3

import argparse

from artiq.devices.lda.driver import Lda, Ldasim
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for the Lab Brick Digital Attenuator")
    parser.add_argument("-P", "--product", default="LDA-102",
                        help="product type (default: %(default)s)",
                        choices=["LDA-102", "LDA-602"])
    simple_network_args(parser, 3253)
    parser.add_argument("-d", "--device", default=None,
                        help="USB serial number of the device. "
                             "The serial number is written on a sticker under "
                             "the device, you should write for example "
                             "-d \"SN:03461\". You must prepend enough 0s for "
                             "it to be 5 digits. If omitted, the first "
                             "available device will be used.")
    parser.add_argument("--simulation", action="store_true",
                        help="Put the driver in simulation mode.")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)
    if args.simulation:
        lda = Ldasim()
    else:
        lda = Lda(args.device, args.product)
    try:
        simple_server_loop({"lda": lda},
                           args.bind, args.port)
    finally:
        lda.close()

if __name__ == "__main__":
    main()
