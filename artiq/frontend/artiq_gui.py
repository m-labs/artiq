#!/usr/bin/env python3

import argparse
import asyncio
import atexit

import gbulb
from gi.repository import Gtk

from artiq.protocols.file_db import FlatFileDB
from artiq.protocols.pc_rpc import AsyncioClient
from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import LayoutManager
from artiq.gui.scheduler import SchedulerWindow
from artiq.gui.parameters import ParametersWindow
from artiq.gui.rt_results import RTResults
from artiq.gui.explorer import ExplorerWindow


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

    # share the schedule control and repository connections
    schedule_ctl = AsyncioClient()
    loop.run_until_complete(schedule_ctl.connect_rpc(
        args.server, args.port_control, "master_schedule"))
    atexit.register(lambda: schedule_ctl.close_rpc())
    repository = AsyncioClient()
    loop.run_until_complete(repository.connect_rpc(
        args.server, args.port_control, "master_repository"))
    atexit.register(lambda: repository.close_rpc())

    scheduler_win = lmgr.create_window(SchedulerWindow,
                                       "scheduler",
                                       schedule_ctl)
    loop.run_until_complete(scheduler_win.sub_connect(
        args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(scheduler_win.sub_close()))

    parameters_win = lmgr.create_window(ParametersWindow, "parameters")
    loop.run_until_complete(parameters_win.sub_connect(
        args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(parameters_win.sub_close()))

    parameters_sub = Subscriber("parameters",
                                parameters_win.init_parameters_store)
    loop.run_until_complete(
        parameters_sub.connect(args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(parameters_sub.close()))

    def exit(*args):
        lmgr.save()
        Gtk.main_quit(*args)
    explorer_win = lmgr.create_window(ExplorerWindow,
                                      "explorer",
                                      exit,
                                      schedule_ctl,
                                      repository)
    loop.run_until_complete(explorer_win.sub_connect(
        args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(explorer_win.sub_close()))
    scheduler_win.show_all()
    parameters_win.show_all()
    explorer_win.show_all()

    rtr = RTResults()
    loop.run_until_complete(rtr.sub_connect(
        args.server, args.port_notify))
    atexit.register(
        lambda: loop.run_until_complete(rtr.sub_close()))

    loop.run_forever()

if __name__ == "__main__":
    main()
