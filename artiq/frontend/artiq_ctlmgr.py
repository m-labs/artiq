#!/usr/bin/env python3

import asyncio
import argparse
import os
import logging

from artiq.protocols.sync_struct import Subscriber
from artiq.tools import verbosity_args, init_logger


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller manager")
    verbosity_args(parser)
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port", default=3250, type=int,
        help="TCP port to use to connect to the master")
    parser.add_argument(
        "--retry-master", default=5.0, type=float,
        help="retry timer for reconnecting to master")
    return parser


class Controllers:
    def __setitem__(self, k, v):
        print("set {} {}".format(k, v))

    def __delitem__(self, k):
        print("del {}".format(k))

    def delete_all(self):
        print("delete all")


class ControllerDB:
    def __init__(self):
        self.current_controllers = Controllers()

    def sync_struct_init(self, init):
        if self.current_controllers is not None:
            self.current_controllers.delete_all()
        for k, v in init.items():
            self.current_controllers[k] = v


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    controller_db = ControllerDB()

    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    try:
        subscriber = Subscriber("devices", controller_db.sync_struct_init)
        while True:
            try:
                loop.run_until_complete(
                    subscriber.connect(args.server, args.port))
                try:
                    loop.run_until_complete(subscriber.receive_task)
                finally:
                    loop.run_until_complete(subscriber.close())
            except (ConnectionAbortedError, ConnectionError,
                    ConnectionRefusedError, ConnectionResetError) as e:
                logger.warning("Connection to master failed (%s: %s)",
                    e.__class__.__name__, str(e))
            else:
                logger.warning("Connection to master lost")
            logger.warning("Retrying in %.1f seconds", args.retry_master)
            loop.run_until_complete(asyncio.sleep(args.retry_master))
    finally:
        loop.close()
        controller_db.current_controllers.delete_all()

if __name__ == "__main__":
    main()
