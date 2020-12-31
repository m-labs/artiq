#!/usr/bin/env python3

import argparse
import asyncio
import struct
import logging
import re

from sipyco.pc_rpc import Server
from sipyco import common_args
from sipyco.logging_tools import log_with_name

from artiq.coredevice.comm_mgmt import Request, Reply


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
    reader, writer = await asyncio.open_connection(host, 1380)
    writer.write(b"ARTIQ management\n")
    writer.write(struct.pack("B", Request.PullLog.value))
    await writer.drain()

    while True:
        length, = struct.unpack(">l", await reader.readexactly(4))
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


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    loop = asyncio.get_event_loop()
    try:
        get_logs_task = asyncio.ensure_future(
            get_logs_sim(args.core_addr) if args.simulation else get_logs(args.core_addr))
        try:
            server = Server({"corelog": PingTarget()}, None, True)
            loop.run_until_complete(server.start(common_args.bind_address_from_args(args), args.port))
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
