#!/usr/bin/env python3

import argparse
import socket
import struct
import os


def send_file(sock, filename):
    with open(filename, "rb") as input_file:
        sock.sendall(struct.pack(">I", os.fstat(input_file.fileno()).st_size))
        while True:
            data = input_file.read(4096)
            if not data:
                break
            sock.sendall(data)
        sock.sendall(b"OK")


def main():
    parser = argparse.ArgumentParser(description="ARTIQ netboot tool")
    parser.add_argument("hostname", metavar="HOSTNAME",
                        help="hostname of the target board")
    parser.add_argument("-f", "--firmware", nargs=1,
                        help="firmware to load")
    # Note that on softcore systems, the main gateware cannot be replaced
    # with -g. This option is used for loading the RTM FPGA from the AMC
    # on Sayma, and the PL on Zynq.
    parser.add_argument("-g", "--gateware", nargs=1,
                        help="gateware to load")
    parser.add_argument("-b", "--boot", action="store_true",
                        help="boot the device")
    args = parser.parse_args()

    sock = socket.create_connection((args.hostname, 4269))
    try:
        if args.firmware is not None:
            sock.sendall(b"F")
            send_file(sock, args.firmware[0])
        if args.gateware is not None:
            sock.sendall(b"G")
            send_file(sock, args.gateware[0])
        if args.boot:
            sock.sendall(b"B")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
