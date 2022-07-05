#!/usr/bin/env python3

import argparse
import asyncio
import struct
import logging
import re

from sipyco.pc_rpc import Server
from sipyco import common_args
from sipyco.logging_tools import log_with_name
from sipyco.asyncio_tools import SignalHandler
from sipyco.keepalive import async_open_connection

from artiq.coredevice.comm_mgmt import Request, Reply

logger = logging.getLogger(__name__)

def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for core device logs")
    common_args.verbosity_args(parser)
    common_args.simple_network_args(parser, 1068)
    parser.add_argument("--simulation", action="store_true",
                        help="Simulation - does not connect to device")
    parser.add_argument("core_addr", metavar="CORE_ADDR",
                        help="hostname or IP address of the core device")
    return parser


class PingTarget:
    def ping(self):
        return True


async def get_logs_sim(host):
    while True:
        await asyncio.sleep(2)
        log_with_name("firmware.simulation", logging.INFO, "hello " + host)


async def get_logs(host):
    try:
        reader, writer = await async_open_connection(
            host,
            1380,
            after_idle=1,
            interval=1,
            max_fails=3,
        )
        writer.write(b"ARTIQ management\n")
        endian = await reader.readexactly(1)
        if endian == b"e":
            endian = "<"
        elif endian == b"E":
            endian = ">"
        else:
            raise IOError("Incorrect reply from device: expected e/E.")
        writer.write(struct.pack("B", Request.PullLog.value))
        await writer.drain()

        while True:
            length, = struct.unpack(endian + "l", await reader.readexactly(4))
            log = await reader.readexactly(length)

            for line in log.decode("utf-8").splitlines():
                m = re.match(r"^\[.+?\] (TRACE|DEBUG| INFO| WARN|ERROR)\((.+?)\): (.+)$", line)
                levelname = m.group(1)
                if levelname == 'TRACE':
                    level = logging.TRACE
                elif levelname == 'DEBUG':
                    level = logging.DEBUG
                elif levelname == ' INFO':
                    level = logging.INFO
                elif levelname == ' WARN':
                    level = logging.WARN
                elif levelname == 'ERROR':
                    level = logging.ERROR
                name = 'firmware.' + m.group(2).replace('::', '.')
                text = m.group(3)
                log_with_name(name, level, text)
    except asyncio.CancelledError:
        raise
    except:
        logger.error("Logging connection terminating with exception", exc_info=True)


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        signal_handler = SignalHandler()
        signal_handler.setup()
        try:
            get_logs_task = asyncio.ensure_future(
                get_logs_sim(args.core_addr) if args.simulation else get_logs(args.core_addr))
            try:
                server = Server({"corelog": PingTarget()}, None, True)
                loop.run_until_complete(server.start(common_args.bind_address_from_args(args), args.port))
                try:
                    _, pending = loop.run_until_complete(asyncio.wait(
                        [signal_handler.wait_terminate(),
                         server.wait_terminate(),
                         get_logs_task],
                        return_when=asyncio.FIRST_COMPLETED))
                    for task in pending:
                        task.cancel()
                finally:
                    loop.run_until_complete(server.stop())
            finally:
                pass
        finally:
            signal_handler.teardown()
    finally:
        loop.close()

if __name__ == "__main__":
    main()
