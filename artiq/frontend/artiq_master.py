#!/usr/bin/env python3

import asyncio
import argparse
import atexit
import os

from artiq.protocols.pc_rpc import Server
from artiq.protocols.sync_struct import Publisher
from artiq.protocols.file_db import FlatFileDB, SimpleHistory
from artiq.master.scheduler import Scheduler
from artiq.master.results import RTResults, get_last_rid
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
        help="TCP port to listen to for notifications (default: 3250)")
    group.add_argument(
        "--port-control", default=3251, type=int,
        help="TCP port to listen to for control (default: 3251)")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()

    init_logger(args)
    ddb = FlatFileDB("ddb.pyon")
    pdb = FlatFileDB("pdb.pyon")
    simplephist = SimpleHistory(30)
    pdb.hooks.append(simplephist)
    rtr = RTResults()
    repository = Repository()
    explist = FlatFileDB("explist.pyon")

    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.close())

    def run_cb(rid, run_params):
        rtr.current_group = run_params["rtr_group"]
    scheduler = Scheduler(run_cb, get_last_rid() + 1)
    scheduler.worker.handlers = {
        "req_device": ddb.request,
        "req_parameter": pdb.request,
        "set_parameter": pdb.set,
        "init_rt_results": rtr.init,
        "update_rt_results": rtr.update,
        "scheduler_run_queued": scheduler.run_queued,
        "scheduler_cancel_queued": scheduler.cancel_queued,
        "scheduler_run_timed": scheduler.run_timed,
        "scheduler_cancel_timed": scheduler.cancel_timed,
    }
    loop.run_until_complete(scheduler.start())
    atexit.register(lambda: loop.run_until_complete(scheduler.stop()))

    server_control = Server({
        "master_ddb": ddb,
        "master_pdb": pdb,
        "master_schedule": scheduler,
        "master_repository": repository,
        "master_explist": explist
    })
    loop.run_until_complete(server_control.start(
        args.bind, args.port_control))
    atexit.register(lambda: loop.run_until_complete(server_control.stop()))

    server_notify = Publisher({
        "queue": scheduler.queue,
        "timed": scheduler.timed,
        "devices": ddb.data,
        "parameters": pdb.data,
        "parameters_simplehist": simplephist.history,
        "rt_results": rtr.groups,
        "explist": explist.data
    })
    loop.run_until_complete(server_notify.start(
        args.bind, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(server_notify.stop()))

    loop.run_forever()

if __name__ == "__main__":
    main()
