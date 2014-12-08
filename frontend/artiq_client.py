#!/usr/bin/env python3

import argparse

from artiq.management.pc_rpc import Client


def _get_args():
    parser = argparse.ArgumentParser(description="ARTIQ client")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port", default=8888, type=int,
        help="TCP port to use to connect to the master")

    subparsers = parser.add_subparsers(dest="action")

    parser_add = subparsers.add_parser("add", help="add an experiment")
    parser_add.add_argument(
        "-p", "--periodic", default=None, type=float,
        help="run the experiment periodically every given number of seconds")
    parser_add.add_argument(
        "-t", "--timeout", default=None, type=float,
        help="specify a timeout for the experiment to complete")
    parser_add.add_argument("-f", "--function", default="run",
                            help="function to run")
    parser_add.add_argument("-u", "--unit", default=None,
                            help="unit to run")
    parser_add.add_argument("file", help="file containing the unit to run")

    return parser.parse_args()


def main():
    args = _get_args()
    remote = Client(args.server, args.port, "master")
    try:
        if args.action == "add":
            if args.periodic is None:
                remote.run_once(
                    {
                        "file": args.file,
                        "unit": args.unit,
                        "function": args.function
                    }, args.timeout)
            else:
                raise NotImplementedError
    finally:
        remote.close_rpc()

if __name__ == "__main__":
    main()
