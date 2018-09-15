#!/usr/bin/env python3

import argparse
import asyncio

from artiq.coredevice.comm_moninj import *


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ RTIO monitor")
    parser.add_argument("core_addr", metavar="CORE_ADDR",
                        help="hostname or IP address of the core device")
    parser.add_argument("channel", metavar="CHANNEL", type=lambda x: int(x, 0), nargs="+",
                       help="channel(s) to monitor")
    return parser


def main():
    args = get_argparser().parse_args()
    
    loop = asyncio.get_event_loop()
    try:
        comm = CommMonInj(
            lambda channel, probe, value: print("0x{:06x}: {}".format(channel, value)),
            lambda channel, override, value: None)
        loop.run_until_complete(comm.connect(args.core_addr))
        try:
            for channel in args.channel:
                comm.monitor_probe(True, channel, 0)
            loop.run_forever()
        finally:
            loop.run_until_complete(comm.close())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
