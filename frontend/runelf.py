#!/usr/bin/env python3

import argparse
from artiq.coredevice import comm_serial


def main():
    parser = argparse.ArgumentParser(description="Core device ELF loading tool")
    parser.add_argument("-e", default=False, action="store_true",
                        help="show environment")
    parser.add_argument("-f", default="run",
                        help="function to run")
    parser.add_argument("file",
                        help="ELF binary to load")
    args = parser.parse_args()

    with open(args.file, "rb") as f:
        binary = f.read()
    with comm_serial.CoreCom() as comm:
        runtime_env = comm.get_runtime_env()
        if args.e:
            print(runtime_env)
        comm.load(binary)
        comm.run(args.f)
        comm.serve(dict(), dict())

if __name__ == "__main__":
    main()
