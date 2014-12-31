#!/usr/bin/env python3

import argparse
import asyncio

import gbulb
from gi.repository import Gtk

from artiq.gui.scheduler import SchedulerWindow
from artiq.gui.parameters import ParametersWindow


def _get_args():
    parser = argparse.ArgumentParser(description="ARTIQ GUI client")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port-notify", default=8887, type=int,
        help="TCP port to connect to for notifications")
    parser.add_argument(
        "--port-control", default=8888, type=int,
        help="TCP port to connect to for control")
    return parser.parse_args()


def main():
    args = _get_args()

    asyncio.set_event_loop_policy(gbulb.GtkEventLoopPolicy())
    loop = asyncio.get_event_loop()
    try:
        scheduler_win = SchedulerWindow()
        scheduler_win.connect("delete-event", Gtk.main_quit)
        scheduler_win.show_all()

        parameters_win = ParametersWindow()
        parameters_win.connect("delete-event", Gtk.main_quit)
        parameters_win.show_all()

        loop.run_until_complete(scheduler_win.sub_connect(
            args.server, args.port_notify))
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(scheduler_win.sub_close())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
