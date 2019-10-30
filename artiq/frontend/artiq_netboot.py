#!/usr/bin/env python3

import argparse
import socket
import struct
import os
import time

def main():
    parser = argparse.ArgumentParser(description="ARTIQ netboot tool")
    parser.add_argument("hostname", metavar="HOSTNAME",
                        help="hostname of the target board")
    parser.add_argument("-f", "--firmware", nargs=1,
                        help="firmware to load")
    parser.add_argument("-b", "--boot", action="store_true",
                        help="boot the device")
    args = parser.parse_args()

    sock = socket.create_connection((args.hostname, 4269))
    try:
        if args.firmware is not None:
            with open(args.firmware[0], "rb") as input_file:
                sock.sendall(b"F")
                sock.sendall(struct.pack(">I", os.fstat(input_file.fileno()).st_size))
                while True:
                    data = input_file.read(4096)
                    if not data:
                        break
                    sock.sendall(data)
                sock.sendall(b"OK")
        if args.boot:
            sock.sendall(b"B")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
