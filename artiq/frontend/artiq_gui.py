#!/usr/bin/env python3

import argparse
import asyncio
import atexit

import gbulb
from gi.repository import Gtk

from artiq.protocols.file_db import FlatFileDB
from artiq.protocols.pc_rpc import AsyncioClient
from artiq.gui.tools import LayoutManager
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
    parser.add_argument(
        "--db-file", default="artiq_gui.pyon",
        help="database file for local GUI settings")
    return parser


def main():
    args = get_argparser().parse_args()

    db = FlatFileDB(args.db_file, default_data=dict())
    lmgr = LayoutManager(db)

    asyncio.set_event_loop_policy(gbulb.GtkEventLoopPolicy())
    loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.close())

    # share the schedule control connection
    schedule_ctl = AsyncioClient()
    loop.run_until_complete(schedule_ctl.connect_rpc(
        args.server, args.port_control, "master_schedule"))
    atexit.register(lambda: schedule_ctl.close_rpc())

    scheduler_win = lmgr.create_window(SchedulerWindow,
                                       "scheduler",
                                       schedule_ctl)
    scheduler_win.connect("delete-event", Gtk.main_quit)
    scheduler_win.show_all()
    loop.run_until_complete(scheduler_win.sub_connect(
        args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(scheduler_win.sub_close()))

    parameters_win = lmgr.create_window(ParametersWindow,
                                        "parameters")
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

    lmgr.save()

if __name__ == "__main__":
    main()
