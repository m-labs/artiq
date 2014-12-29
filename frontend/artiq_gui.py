#!/usr/bin/env python3

import argparse
import asyncio

import gbulb
from gi.repository import Gtk

from artiq.management.sync_struct import Subscriber


class QueueStoreSyncer:
    def __init__(self, queue_store, init):
        self.queue_store = queue_store
        self.queue_store.clear()
        for x in init:
            self.append(x)

    def _convert(self, x):
        rid, run_params, timeout = x
        row = [rid, run_params["file"]]
        for x in run_params["unit"], run_params["function"], timeout:
            row.append("-" if x is None else str(x))
        return row

    def append(self, x):
        self.queue_store.append(self._convert(x))

    def insert(self, i, x):
        self.queue_store.insert(i, self._convert(x))

    def __delitem__(self, key):
        del self.queue_store[key]


class SchedulerWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Scheduler")

        self.queue_store = Gtk.ListStore(int, str, str, str, str)
        tree = Gtk.TreeView(self.queue_store)
        for i, title in enumerate(["RID", "File", "Unit",
                                   "Function", "Timeout"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            tree.append_column(column)
        self.add(tree)

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.subscriber = Subscriber(self.init_queue_store)
        yield from self.subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.subscriber.close()

    def init_queue_store(self, init):
        return QueueStoreSyncer(self.queue_store, init)


def _get_args():
    parser = argparse.ArgumentParser(description="ARTIQ GUI client")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port-schedule-control", default=8888, type=int,
        help="TCP port to connect to for schedule control")
    parser.add_argument(
        "--port-schedule-notify", default=8887, type=int,
        help="TCP port to connect to for schedule notifications")
    return parser.parse_args()


def main():
    args = _get_args()

    asyncio.set_event_loop_policy(gbulb.GtkEventLoopPolicy())
    loop = asyncio.get_event_loop()
    try:
        win = SchedulerWindow()
        win.connect("delete-event", Gtk.main_quit)
        win.show_all()

        loop.run_until_complete(win.sub_connect(args.server,
                                                args.port_schedule_notify))
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(win.sub_close())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
