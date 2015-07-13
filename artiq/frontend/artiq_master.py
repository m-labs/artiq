#!/usr/bin/env python3

import asyncio
import argparse
import atexit
import os

from artiq.protocols.pc_rpc import Server
from artiq.protocols.sync_struct import Notifier, Publisher, process_mod
from artiq.protocols.file_db import FlatFileDB
from artiq.master.scheduler import Scheduler
from artiq.master.worker_db import get_last_rid
from artiq.master.repository import Repository
from artiq.tools import verbosity_args, init_logger


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ master")
    group = parser.add_argument_group("network")
    group.add_argument(
        "--bind", default="::1",
        help="hostname or IP address to bind to")
    group.add_argument(
        "--port-notify", default=3250, type=int,
        help="TCP port to listen to for notifications (default: %(default)d)")
    group.add_argument(
        "--port-control", default=3251, type=int,
        help="TCP port to listen to for control (default: %(default)d)")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()

    init_logger(args)
    ddb = FlatFileDB("ddb.pyon")
    pdb = FlatFileDB("pdb.pyon")
    rtr = Notifier(dict())
    repository = Repository()

    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.close())

    worker_handlers = {
        "get_device": ddb.get,
        "get_parameter": pdb.get,
        "set_parameter": pdb.set,
        "update_rt_results": lambda mod: process_mod(rtr, mod),
    }
    scheduler = Scheduler(get_last_rid() + 1, worker_handlers)
    worker_handlers["scheduler_submit"] = scheduler.submit
    scheduler.start()
    atexit.register(lambda: loop.run_until_complete(scheduler.stop()))

    server_control = Server({
        "master_ddb": ddb,
        "master_pdb": pdb,
        "master_schedule": scheduler,
        "master_repository": repository,
    })
    loop.run_until_complete(server_control.start(
        args.bind, args.port_control))
    atexit.register(lambda: loop.run_until_complete(server_control.stop()))

    server_notify = Publisher({
        "schedule": scheduler.notifier,
        "devices": ddb.data,
        "parameters": pdb.data,
        "rt_results": rtr,
        "explist": repository.explist
    })
    loop.run_until_complete(server_notify.start(
        args.bind, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(server_notify.stop()))

    loop.run_forever()

if __name__ == "__main__":
    main()
