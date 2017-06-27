#!/usr/bin/env python3

import argparse
import asyncio

from artiq.protocols.pc_rpc import Server
from artiq.tools import *


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for core device logs")
    simple_network_args(parser, 1068)
    parser.add_argument("core_addr",
                        help="hostname or IP address of the core device")
    verbosity_args(parser)
    return parser


class PingTarget:
    def ping(self):
        return True


async def get_logs(host):
    while True:
        print("TODO: not implemented. host:", host)
        await asyncio.sleep(2)


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    loop = asyncio.get_event_loop()
    try:
        get_logs_task = asyncio.ensure_future(get_logs(args.core_addr))
        try:
            server = Server({"corelog": PingTarget()}, None, True)
            loop.run_until_complete(server.start(bind_address_from_args(args), args.port))
            try:
                loop.run_until_complete(server.wait_terminate())
            finally:
                loop.run_until_complete(server.stop())
        finally:
            get_logs_task.cancel()
            try:
                loop.run_until_complete(get_logs_task)
            except asyncio.CancelledError:
                pass
    finally:
        loop.close()

if __name__ == "__main__":
    main()
