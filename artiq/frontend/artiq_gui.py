#!/usr/bin/env python3

import argparse
import asyncio
import atexit

import gbulb
from gi.repository import Gtk

from artiq.protocols.pc_rpc import AsyncioClient
from artiq.gui.scheduler import SchedulerWindow
from artiq.gui.parameters import ParametersWindow
from artiq.gui.rt_results import RTResults


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ GUI client")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port-notify", default=3250, type=int,
        help="TCP port to connect to for notifications")
    parser.add_argument(
        "--port-control", default=3251, type=int,
        help="TCP port to connect to for control")
    return parser


def main():
    args = get_argparser().parse_args()

    asyncio.set_event_loop_policy(gbulb.GtkEventLoopPolicy())
    loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.close())

    # share the schedule control connection
    schedule_ctl = AsyncioClient()
    loop.run_until_complete(schedule_ctl.connect_rpc(
        args.server, args.port_control, "master_schedule"))
    atexit.register(lambda: schedule_ctl.close_rpc())

    scheduler_win = SchedulerWindow(schedule_ctl)
    scheduler_win.connect("delete-event", Gtk.main_quit)
    scheduler_win.show_all()
    loop.run_until_complete(scheduler_win.sub_connect(
        args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(scheduler_win.sub_close()))

    parameters_win = ParametersWindow()
    parameters_win.connect("delete-event", Gtk.main_quit)
    parameters_win.show_all()
    loop.run_until_complete(parameters_win.sub_connect(
        args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(parameters_win.sub_close()))

    rtr = RTResults()
    loop.run_until_complete(rtr.sub_connect(
        args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(rtr.sub_close()))


    loop.run_forever()

if __name__ == "__main__":
    main()
