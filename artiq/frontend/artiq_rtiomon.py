#!/usr/bin/env python3

import argparse
import asyncio

from sipyco.asyncio_tools import SignalHandler

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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        signal_handler = SignalHandler()
        signal_handler.setup()
        try:
            comm = CommMonInj(
                lambda channel, probe, value: print("0x{:06x}: {}".format(channel, value)),
                lambda channel, override, value: None)
            loop.run_until_complete(comm.connect(args.core_addr))
            try:
                for channel in args.channel:
                    comm.monitor_probe(True, channel, 0)
                loop.run_until_complete(signal_handler.wait_terminate())
            finally:
                loop.run_until_complete(comm.close())
        finally:
            signal_handler.teardown()
    finally:
        loop.close()


if __name__ == "__main__":
    main()
