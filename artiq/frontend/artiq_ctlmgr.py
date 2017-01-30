#!/usr/bin/env python3

import asyncio
import atexit
import argparse
import os
import logging
import platform

from artiq.protocols.pc_rpc import Server
from artiq.protocols.logging import LogForwarder, SourceFilter
from artiq.tools import (simple_network_args, atexit_register_coroutine,
                         bind_address_from_args)
from artiq.devices.ctlmgr import ControllerManager


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller manager")

    group = parser.add_argument_group("verbosity")
    group.add_argument("-v", "--verbose", default=0, action="count",
                       help="increase logging level of the manager process")
    group.add_argument("-q", "--quiet", default=0, action="count",
                       help="decrease logging level of the manager process")

    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port-notify", default=3250, type=int,
        help="TCP port to connect to for notifications")
    parser.add_argument(
        "--port-logging", default=1066, type=int,
        help="TCP port to connect to for logging")
    parser.add_argument(
        "--retry-master", default=5.0, type=float,
        help="retry timer for reconnecting to master")
    simple_network_args(parser, [("control", "control", 3249)])
    return parser


def main():
    args = get_argparser().parse_args()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)
    source_adder = SourceFilter(logging.WARNING +
                                args.quiet*10 - args.verbose*10,
                                "ctlmgr({})".format(platform.node()))
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)s:%(source)s:%(name)s:%(message)s"))
    console_handler.addFilter(source_adder)
    root_logger.addHandler(console_handler)

    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    atexit.register(loop.close)

    logfwd = LogForwarder(args.server, args.port_logging,
                          args.retry_master)
    logfwd.addFilter(source_adder)
    root_logger.addHandler(logfwd)
    logfwd.start()
    atexit_register_coroutine(logfwd.stop)

    ctlmgr = ControllerManager(args.server, args.port_notify,
                               args.retry_master)
    ctlmgr.start()
    atexit_register_coroutine(ctlmgr.stop)

    class CtlMgrRPC:
        retry_now = ctlmgr.retry_now

    rpc_target = CtlMgrRPC()
    rpc_server = Server({"ctlmgr": rpc_target}, builtin_terminate=True)
    loop.run_until_complete(rpc_server.start(bind_address_from_args(args),
                                             args.port_control))
    atexit_register_coroutine(rpc_server.stop)

    loop.run_until_complete(rpc_server.wait_terminate())


if __name__ == "__main__":
    main()
