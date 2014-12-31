#!/usr/bin/env python3

import asyncio
import argparse
import atexit

from artiq.management.pc_rpc import Server
from artiq.management.sync_struct import Publisher
from artiq.management.dpdb import DeviceParamDB
from artiq.management.scheduler import Scheduler


def _get_args():
    parser = argparse.ArgumentParser(description="ARTIQ master")
    parser.add_argument(
        "--bind", default="::1",
        help="hostname or IP address to bind to")
    parser.add_argument(
        "--port-schedule-control", default=8888, type=int,
        help="TCP port to listen to for schedule control")
    parser.add_argument(
        "--port-schedule-notify", default=8887, type=int,
        help="TCP port to listen to for schedule notifications")
    return parser.parse_args()


def main():
    args = _get_args()
    dpdb = DeviceParamDB("ddb.pyon", "pdb.pyon")

    loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.close())

    scheduler = Scheduler({
        "req_device": dpdb.req_device,
        "req_parameter": dpdb.req_parameter
    })
    loop.run_until_complete(scheduler.start())
    atexit.register(lambda: loop.run_until_complete(scheduler.stop()))

    schedule_control = Server(scheduler, "schedule_control")
    loop.run_until_complete(schedule_control.start(
        args.bind, args.port_schedule_control))
    atexit.register(lambda: loop.run_until_complete(schedule_control.stop()))

    schedule_notify = Publisher({
        "queue": scheduler.queue,
        "periodic": scheduler.periodic
    })
    loop.run_until_complete(schedule_notify.start(
        args.bind, args.port_schedule_notify))
    atexit.register(lambda: loop.run_until_complete(schedule_notify.stop()))

    loop.run_forever()

if __name__ == "__main__":
    main()
