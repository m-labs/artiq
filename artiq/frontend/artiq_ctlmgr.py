#!/usr/bin/env python3

import asyncio
import argparse
import os

from artiq.protocols.sync_struct import Subscriber


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller manager")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port", default=3250, type=int,
        help="TCP port to use to connect to the master")
    return parser


def main():
    args = get_argparser().parse_args()

    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    try:
        subscriber = Subscriber("master_ddb", lambda x: x)
        loop.run_until_complete(subscriber.connect(args.server, args.port))
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(subscriber.close())
    finally:
        loop.close()    

if __name__ == "__main__":
    main()
