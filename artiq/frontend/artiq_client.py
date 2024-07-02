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
import numpy as np

from prettytable import PrettyTable

from sipyco.pc_rpc import Client
from sipyco.sync_struct import Subscriber
from sipyco.broadcast import Receiver
from sipyco import common_args, pyon
from sipyco.asyncio_tools import SignalHandler

from artiq.tools import (scale_from_metadata, short_format, parse_arguments,
                         parse_devarg_override)
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
        help="hostname or IP of the master to connect to (default: %(default)s)")
    parser.add_argument(
        "--port", default=None, type=int,
        help="TCP port to use to connect to the master (default: %(default)s)")
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
                                 "scheduling default: %(default)s)")
    parser_add.add_argument("-t", "--timed", default=None, type=str,
                            help="set a due date for the experiment "
                            "(default: %(default)s)")
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
    parser_add.add_argument("--devarg-override", default="",
                            help="specify device arguments to override")
    parser_add.add_argument("--content", default=False,
                            action="store_true",
                            help="submit by content")
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
    parser_set_dataset.add_argument("--unit", default=None, type=str,
                                    help="physical unit of the dataset (default: %(default)s)")
    parser_set_dataset.add_argument("--scale", default=None, type=float,
                                    help="factor to multiply value of dataset in displays "
                                    "(default: %(default)s)")
    parser_set_dataset.add_argument("--precision", default=None, type=int,
                                    help="maximum number of decimals to print in displays "
                                    "(default: %(default)s)")

    persist_group = parser_set_dataset.add_mutually_exclusive_group()
    persist_group.add_argument("-p", "--persist", action="store_true",
                               help="make the dataset persistent")
    persist_group.add_argument("-n", "--no-persist", action="store_true",
                               help="make the dataset non-persistent")

    parser_del_dataset = subparsers.add_parser(
        "del-dataset", help="delete a dataset")
    parser_del_dataset.add_argument("name", help="name of the dataset")

    parser_supply_interactive = subparsers.add_parser(
        "supply-interactive", help="supply interactive arguments")
    parser_supply_interactive.add_argument(
        "rid", metavar="RID", type=int, help="RID of target experiment")
    parser_supply_interactive.add_argument(
        "arguments", metavar="ARGUMENTS", nargs="*",
        help="interactive arguments")

    parser_cancel_interactive = subparsers.add_parser(
        "cancel-interactive", help="cancel interactive arguments")
    parser_cancel_interactive.add_argument(
        "rid", metavar="RID", type=int, help="RID of target experiment")

    parser_show = subparsers.add_parser(
        "show", help="show schedule, log, devices or datasets")
    parser_show.add_argument(
        "what", metavar="WHAT",
        choices=["schedule", "log", "ccb", "devices", "datasets",
                 "interactive-args"],
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

    subparsers.add_parser("terminate", help="terminate the ARTIQ master")

    common_args.verbosity_args(parser)
    return parser


def _action_submit(remote, args):
    try:
        arguments = parse_arguments(args.arguments)
    except Exception as err:
        raise ValueError("Failed to parse run arguments") from err

    expid = {
        "devarg_override": parse_devarg_override(args.devarg_override),
        "log_level": logging.WARNING + args.quiet*10 - args.verbose*10,
        "class_name": args.class_name,
        "arguments": arguments,
    }
    if args.content:
        with open(args.file, "r") as f:
            expid["content"] = f.read()
        if args.repository:
            raise ValueError("Repository cannot be used when submitting by content")
    else:
        expid["file"] = args.file
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
    metadata = {}
    if args.unit is not None:
        metadata["unit"] = args.unit
    if args.scale is not None:
        metadata["scale"] = args.scale
    if args.precision is not None:
        metadata["precision"] = args.precision
    scale = scale_from_metadata(metadata)
    value = pyon.decode(args.value)
    t = type(value)
    if np.issubdtype(t, np.number) or t is np.ndarray:
        value = value * scale
    remote.set(args.name, value, persist, metadata)


def _action_del_dataset(remote, args):
    remote.delete(args.name)


def _action_scan_devices(remote, args):
    remote.scan()


def _action_supply_interactive(remote, args):
    arguments = parse_arguments(args.arguments)
    remote.supply(args.rid, arguments)


def _action_cancel_interactive(remote, args):
    remote.cancel(args.rid)


def _action_scan_repository(remote, args):
    if getattr(args, "async"):
        remote.scan_repository_async(args.revision)
    else:
        remote.scan_repository(args.revision)


def _action_ls(remote, args):
    contents = remote.list_directory(args.directory)
    for name in sorted(contents, key=lambda x: (x[-1] not in "\\/", x)):
        print(name)


def _action_terminate(remote, _args):
    remote.terminate()


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
            row.append(expid.get("file", "<none>"))
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
    for k, (persist, value, metadata) in sorted(datasets.items(), key=itemgetter(0)):
        table.add_row([k, "Y" if persist else "N", short_format(value, metadata)])
    print(table)


def _show_interactive_args(interactive_args):
    clear_screen()
    table = PrettyTable(["RID", "Title", "Key", "Type", "Group", "Tooltip"])
    for rid, input_request in sorted(interactive_args.items(), key=itemgetter(0)):
        title = input_request["title"]
        for key, procdesc, group, tooltip in input_request["arglist_desc"]:
            table.add_row([rid, title, key, procdesc["ty"], group, tooltip])
    print(table)


def _run_subscriber(host, port, subscriber):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        signal_handler = SignalHandler()
        signal_handler.setup()
        try:
            loop.run_until_complete(subscriber.connect(host, port))
            try:
                _, pending = loop.run_until_complete(asyncio.wait(
                    [loop.create_task(signal_handler.wait_terminate()), subscriber.receive_task],
                    return_when=asyncio.FIRST_COMPLETED))
                for task in pending:
                    task.cancel()
            finally:
                loop.run_until_complete(subscriber.close())
        finally:
            signal_handler.teardown()
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
        elif args.what == "interactive-args":
            _show_dict(args, "interactive_args", _show_interactive_args)
        else:
            raise ValueError
    else:
        port = 3251 if args.port is None else args.port
        target_name = {
            "submit": "schedule",
            "delete": "schedule",
            "set_dataset": "dataset_db",
            "del_dataset": "dataset_db",
            "scan_devices": "device_db",
            "supply_interactive": "interactive_arg_db",
            "cancel_interactive": "interactive_arg_db",
            "scan_repository": "experiment_db",
            "ls": "experiment_db",
            "terminate": "master_management",
        }[action]
        remote = Client(args.server, port, target_name)
        try:
            globals()["_action_" + action](remote, args)
        finally:
            remote.close_rpc()


if __name__ == "__main__":
    main()
