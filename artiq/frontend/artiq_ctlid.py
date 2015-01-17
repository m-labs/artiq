#!/usr/bin/env python3

import argparse

from artiq.protocols.pc_rpc import Client


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
        target_names, id_parameters = remote.get_rpc_id()
    finally:
        remote.close_rpc()
    print("Target(s):   " + ", ".join(target_names))
    if id_parameters is not None:
        print("Parameters:  " + id_parameters)

if __name__ == "__main__":
    main()
