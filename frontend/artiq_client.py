#!/usr/bin/env python3

import argparse
import time
import asyncio

from prettytable import PrettyTable

from artiq.management.pc_rpc import Client
from artiq.management.sync_struct import Subscriber
from artiq.management.tools import clear_screen


def _get_args():
    parser = argparse.ArgumentParser(description="ARTIQ CLI client")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port", default=None, type=int,
        help="TCP port to use to connect to the master")

    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True

    parser_add = subparsers.add_parser("submit", help="submit an experiment")
    parser_add.add_argument(
        "-p", "--periodic", default=None, type=float,
        help="run the experiment periodically every given number of seconds")
    parser_add.add_argument(
        "-t", "--timeout", default=None, type=float,
        help="specify a timeout for the experiment to complete")
    parser_add.add_argument("-f", "--function", default="run",
                            help="function to run")
    parser_add.add_argument("-u", "--unit", default=None,
                            help="unit to run")
    parser_add.add_argument("file", help="file containing the unit to run")

    parser_cancel = subparsers.add_parser("cancel",
                                          help="cancel an experiment")
    parser_cancel.add_argument("-p", "--periodic", default=False,
                               action="store_true",
                               help="cancel a periodic experiment")
    parser_cancel.add_argument("rid", type=int,
                               help="run identifier (RID/PRID)")

    parser_show_queue = subparsers.add_parser(
        "show-queue", help="show the experiment queue")

    parser_show_periodic = subparsers.add_parser(
        "show-periodic", help="show the periodic experiment table")

    return parser.parse_args()


def _action_submit(remote, args):
    run_params = {
        "file": args.file,
        "unit": args.unit,
        "function": args.function
    }
    if args.periodic is None:
        rid = remote.run_once(run_params, args.timeout)
        print("RID: {}".format(rid))
    else:
        prid = remote.run_periodic(run_params, args.timeout,
                                   args.periodic)
        print("PRID: {}".format(prid))


def _action_cancel(remote, args):
    if args.periodic:
        remote.cancel_periodic(args.rid)
    else:
        remote.cancel_once(args.rid)


def _show_queue(queue):
    clear_screen()
    if queue:
        table = PrettyTable(["RID", "File", "Unit", "Function", "Timeout"])
        for rid, run_params, timeout in queue:
            row = [rid, run_params["file"]]
            for x in run_params["unit"], run_params["function"], timeout:
                row.append("-" if x is None else x)
            table.add_row(row)
        print(table)
    else:
        print("Queue is empty")


def _show_periodic(periodic):
    clear_screen()
    if periodic:
        table = PrettyTable(["Next run", "PRID", "File", "Unit", "Function",
                             "Timeout", "Period"])
        sp = sorted(periodic.items(), key=lambda x: (x[1][0], x[0]))
        for prid, (next_run, run_params, timeout, period) in sp:
            row = [time.strftime("%m/%d %H:%M:%S", time.localtime(next_run)),
                   prid, run_params["file"]]
            for x in run_params["unit"], run_params["function"], timeout:
                row.append("-" if x is None else x)
            row.append(period)
            table.add_row(row)
        print(table)
    else:
        print("No periodic schedule")


def _run_subscriber(host, port, subscriber):
    if port is None:
        port = 8887
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(subscriber.connect(host, port))
        try:
            loop.run_until_complete(asyncio.wait_for(subscriber.receive_task,
                                                     None))
            print("Connection to master lost")
        finally:
            loop.run_until_complete(subscriber.close())
    finally:
        loop.close()


def main():
    args = _get_args()
    if args.action == "show-queue":
        queue = []
        def init_queue(x):
            queue[:] = x
            return queue
        subscriber = Subscriber("queue", init_queue,
                                lambda: _show_queue(queue))
        _run_subscriber(args.server, args.port, subscriber)
    elif args.action == "show-periodic":
        periodic = dict()
        def init_periodic(x):
            periodic.clear()
            periodic.update(x)
            return periodic
        subscriber = Subscriber("periodic", init_periodic,
                                lambda: _show_periodic(periodic))
        _run_subscriber(args.server, args.port, subscriber)
    else:
        port = 8888 if args.port is None else args.port
        remote = Client(args.server, port, "master_schedule")
        try:
            globals()["_action_" + args.action](remote, args)
        finally:
            remote.close_rpc()

if __name__ == "__main__":
    main()
