#!/usr/bin/env python3

import argparse

from artiq.management.pc_rpc import Client


def _get_args():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller identification tool")
    parser.add_argument("server",
                        help="hostname or IP of the controller to connect to")
    parser.add_argument("port", type=int,
                        help="TCP port to use to connect to the controller")
    return parser.parse_args()


def main():
    args = _get_args()
    remote = Client(args.server, args.port, None)
    try:
        ident = remote.get_rpc_id()
    finally:
        remote.close_rpc()
    print("Type:       " + ident["type"])
    if "parameters" in ident:
        print("Parameters: " + ident["parameters"])

if __name__ == "__main__":
    main()
