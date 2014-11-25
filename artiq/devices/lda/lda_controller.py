#!/usr/bin/env python3
from artiq.management.pc_rpc import simple_server_loop
from lda import Lda
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--device', default="LDA-102",
                        choices=["LDA-102", "LDA-602", "sim"])
    parser.add_argument('--bind', default="::1",
                        help="hostname or IP address to bind to")
    parser.add_argument('-p', '--port', default=7777, type=int,
                        help="TCP port to listen to")
    parser.add_argument('-s', '--serial', default=None,
                        help="USB serial number of the device")
    args = parser.parse_args()

    simple_server_loop(Lda(args.serial, args.device), "lda",
                       args.bind, args.port)
