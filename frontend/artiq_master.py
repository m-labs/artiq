#!/usr/bin/env python3

import asyncio
import argparse
import atexit

from artiq.management.pc_rpc import Server
from artiq.management.sync_struct import Publisher
from artiq.management.dpdb import DeviceParamDB, SimpleParameterHistory
from artiq.management.scheduler import Scheduler


def _get_args():
    parser = argparse.ArgumentParser(description="ARTIQ master")
    parser.add_argument(
        "--bind", default="::1",
        help="hostname or IP address to bind to")
    parser.add_argument(
        "--port-notify", default=8887, type=int,
        help="TCP port to listen to for notifications")
    parser.add_argument(
        "--port-control", default=8888, type=int,
        help="TCP port to listen to for control")
    return parser.parse_args()


def main():
    args = _get_args()

    dpdb = DeviceParamDB("ddb.pyon", "pdb.pyon")
    simplephist = SimpleParameterHistory(30)
    dpdb.parameter_hooks.append(simplephist)

    loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.close())

    scheduler = Scheduler({
        "req_device": dpdb.req_device,
        "req_parameter": dpdb.req_parameter,
        "set_parameter": dpdb.set_parameter
    })
    loop.run_until_complete(scheduler.start())
    atexit.register(lambda: loop.run_until_complete(scheduler.stop()))

    server_control = Server({
        "master_schedule": scheduler,
        "master_dpdb": dpdb
    })
    loop.run_until_complete(server_control.start(
        args.bind, args.port_control))
    atexit.register(lambda: loop.run_until_complete(server_control.stop()))

    server_notify = Publisher({
        "queue": scheduler.queue,
        "periodic": scheduler.periodic,
        "devices": dpdb.ddb,
        "parameters": dpdb.pdb,
        "parameters_simplehist": simplephist.history
    })
    loop.run_until_complete(server_notify.start(
        args.bind, args.port_notify))
    atexit.register(lambda: loop.run_until_complete(server_notify.stop()))

    loop.run_forever()

if __name__ == "__main__":
    main()
