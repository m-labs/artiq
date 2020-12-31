#!/usr/bin/env python3
"""
Client to send commands to :mod:`artiq_master` and display results locally.

The client can perform actions such as accessing/setting datasets,
scanning devices, scheduling experiments, and looking for experiments/devices.
"""

import argparse
import logging
import time
import asyncio
import sys
import os
from operator import itemgetter
from dateutil.parser import parse as parse_date

from prettytable import PrettyTable

from sipyco.pc_rpc import Client
from sipyco.sync_struct import Subscriber
from sipyco.broadcast import Receiver
from sipyco import common_args, pyon

from artiq.tools import short_format, parse_arguments
from artiq import __version__ as artiq_version


def clear_screen():
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\x1b[2J\x1b[H")


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ CLI client")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port", default=None, type=int,
        help="TCP port to use to connect to the master")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True

    parser_add = subparsers.add_parser("submit", help="submit an experiment")
    parser_add.add_argument("-p", "--pipeline", default="main", type=str,
                            help="pipeline to run the experiment in "
                                 "(default: %(default)s)")
    parser_add.add_argument("-P", "--priority", default=0, type=int,
                            help="priority (higher value means sooner "
                                 "scheduling, default: %(default)s)")
    parser_add.add_argument("-t", "--timed", default=None, type=str,
                            help="set a due date for the experiment")
    parser_add.add_argument("-f", "--flush", default=False,
                            action="store_true",
                            help="flush the pipeline before preparing "
                            "the experiment")
    parser_add.add_argument("-R", "--repository", default=False,
                            action="store_true",
                            help="use the experiment repository")
    parser_add.add_argument("-r", "--revision", default=None,
                            help="use a specific repository revision "
                                 "(defaults to head, ignored without -R)")
    parser_add.add_argument("-c", "--class-name", default=None,
                            help="name of the class to run")
    parser_add.add_argument("file", metavar="FILE",
                            help="file containing the experiment to run")
    parser_add.add_argument("arguments", metavar="ARGUMENTS", nargs="*",
                            help="run arguments")

    parser_delete = subparsers.add_parser("delete",
                                          help="delete an experiment "
                                               "from the schedule")
    parser_delete.add_argument("-g", action="store_true",
                               help="request graceful termination")
    parser_delete.add_argument("rid", metavar="RID", type=int,
                               help="run identifier (RID)")

    parser_set_dataset = subparsers.add_parser(
        "set-dataset", help="add or modify a dataset")
    parser_set_dataset.add_argument("name", metavar="NAME",
                                    help="name of the dataset")
    parser_set_dataset.add_argument("value", metavar="VALUE",
                                    help="value in PYON format")

    persist_group = parser_set_dataset.add_mutually_exclusive_group()
    persist_group.add_argument("-p", "--persist", action="store_true",
                               help="make the dataset persistent")
    persist_group.add_argument("-n", "--no-persist", action="store_true",
                               help="make the dataset non-persistent")

    parser_del_dataset = subparsers.add_parser(
        "del-dataset", help="delete a dataset")
    parser_del_dataset.add_argument("name", help="name of the dataset")

    parser_show = subparsers.add_parser(
        "show", help="show schedule, log, devices or datasets")
    parser_show.add_argument(
        "what", metavar="WHAT",
        choices=["schedule", "log", "ccb", "devices", "datasets"],
        help="select object to show: %(choices)s")

    subparsers.add_parser(
        "scan-devices", help="trigger a device database (re)scan")

    parser_scan_repos = subparsers.add_parser(
        "scan-repository", help="trigger a repository (re)scan")
    parser_scan_repos.add_argument("--async", action="store_true",
                                   help="trigger scan and return immediately")
    parser_scan_repos.add_argument("revision", metavar="REVISION",
                                   default=None, nargs="?",
                                   help="use a specific repository revision "
                                        "(defaults to head)")

    parser_ls = subparsers.add_parser(
        "ls", help="list a directory on the master")
    parser_ls.add_argument("directory", default="", nargs="?")

    common_args.verbosity_args(parser)
    return parser


def _action_submit(remote, args):
    try:
        arguments = parse_arguments(args.arguments)
    except Exception as err:
        raise ValueError("Failed to parse run arguments") from err

    expid = {
        "log_level": logging.WARNING + args.quiet*10 - args.verbose*10,
        "file": args.file,
        "class_name": args.class_name,
        "arguments": arguments,
    }
    if args.repository:
        expid["repo_rev"] = args.revision
    if args.timed is None:
        due_date = None
    else:
        due_date = time.mktime(parse_date(args.timed).timetuple())
    rid = remote.submit(args.pipeline, expid,
                        args.priority, due_date, args.flush)
    print("RID: {}".format(rid))


def _action_delete(remote, args):
    if args.g:
        remote.request_termination(args.rid)
    else:
        remote.delete(args.rid)


def _action_set_dataset(remote, args):
    persist = None
    if args.persist:
        persist = True
    if args.no_persist:
        persist = False
    remote.set(args.name, pyon.decode(args.value), persist)


def _action_del_dataset(remote, args):
    remote.delete(args.name)


def _action_scan_devices(remote, args):
    remote.scan()


def _action_scan_repository(remote, args):
    if getattr(args, "async"):
        remote.scan_repository_async(args.revision)
    else:
        remote.scan_repository(args.revision)


def _action_ls(remote, args):
    contents = remote.list_directory(args.directory)
    for name in sorted(contents, key=lambda x: (x[-1] not in "\\/", x)):
        print(name)


def _show_schedule(schedule):
    clear_screen()
    if schedule:
        sorted_schedule = sorted(schedule.items(),
                                 key=lambda x: (-x[1]["priority"],
                                                x[1]["due_date"] or 0,
                                                x[0]))
        table = PrettyTable(["RID", "Pipeline", "    Status    ", "Prio",
                             "Due date", "Revision", "File", "Class name"])
        for rid, v in sorted_schedule:
            row = [rid, v["pipeline"], v["status"], v["priority"]]
            if v["due_date"] is None:
                row.append("")
            else:
                row.append(time.strftime("%m/%d %H:%M:%S",
                           time.localtime(v["due_date"])))
            expid = v["expid"]
            if "repo_rev" in expid:
                row.append(expid["repo_rev"])
            else:
                row.append("Outside repo.")
            row.append(expid["file"])
            if expid["class_name"] is None:
                row.append("")
            else:
                row.append(expid["class_name"])
            table.add_row(row)
        print(table)
    else:
        print("Schedule is empty")


def _show_devices(devices):
    clear_screen()
    table = PrettyTable(["Name", "Description"])
    table.align["Description"] = "l"
    for k, v in sorted(devices.items(), key=itemgetter(0)):
        table.add_row([k, pyon.encode(v, True)])
    print(table)


def _show_datasets(datasets):
    clear_screen()
    table = PrettyTable(["Dataset", "Persistent", "Value"])
    for k, (persist, value) in sorted(datasets.items(), key=itemgetter(0)):
        table.add_row([k, "Y" if persist else "N", short_format(value)])
    print(table)


def _run_subscriber(host, port, subscriber):
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


def _show_dict(args, notifier_name, display_fun):
    d = dict()

    def init_d(x):
        d.clear()
        d.update(x)
        return d
    subscriber = Subscriber(notifier_name, init_d,
                            lambda mod: display_fun(d))
    port = 3250 if args.port is None else args.port
    _run_subscriber(args.server, port, subscriber)


def _print_log_record(record):
    level, source, t, message = record
    t = time.strftime("%m/%d %H:%M:%S", time.localtime(t))
    print(level, source, t, message)


def _show_log(args):
    subscriber = Receiver("log", [_print_log_record])
    port = 1067 if args.port is None else args.port
    _run_subscriber(args.server, port, subscriber)


def _show_ccb(args):
    subscriber = Receiver("ccb", [
        lambda d: print(d["service"],
                        "args:", d["args"],
                        "kwargs:", d["kwargs"])
    ])
    port = 1067 if args.port is None else args.port
    _run_subscriber(args.server, port, subscriber)


def main():
    args = get_argparser().parse_args()
    action = args.action.replace("-", "_")
    if action == "show":
        if args.what == "schedule":
            _show_dict(args, "schedule", _show_schedule)
        elif args.what == "log":
            _show_log(args)
        elif args.what == "ccb":
            _show_ccb(args)
        elif args.what == "devices":
            _show_dict(args, "devices", _show_devices)
        elif args.what == "datasets":
            _show_dict(args, "datasets", _show_datasets)
        else:
            raise ValueError
    else:
        port = 3251 if args.port is None else args.port
        target_name = {
            "submit": "master_schedule",
            "delete": "master_schedule",
            "set_dataset": "master_dataset_db",
            "del_dataset": "master_dataset_db",
            "scan_devices": "master_device_db",
            "scan_repository": "master_experiment_db",
            "ls": "master_experiment_db"
        }[action]
        remote = Client(args.server, port, target_name)
        try:
            globals()["_action_" + action](remote, args)
        finally:
            remote.close_rpc()


if __name__ == "__main__":
    main()
