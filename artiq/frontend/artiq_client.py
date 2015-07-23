#!/usr/bin/env python3

import argparse
import time
import asyncio
import sys
from operator import itemgetter
from dateutil.parser import parse as parse_date

from prettytable import PrettyTable

from artiq.protocols.pc_rpc import Client
from artiq.protocols.sync_struct import Subscriber
from artiq.protocols import pyon


def clear_screen():
    sys.stdout.write("\x1b[2J\x1b[H")


def get_argparser():
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
    parser_add.add_argument("-p", "--pipeline", default="main", type=str,
                            help="pipeline to run the experiment in "
                                 "(default: %(default)s)")
    parser_add.add_argument("-P", "--priority", default=0, type=int,
                            help="priority (higher value means sooner "
                                 "scheduling, default: %(default)s)")
    parser_add.add_argument("-t", "--timed", default=None, type=str,
                            help="set a due date for the experiment")
    parser_add.add_argument("-f", "--flush", default=False, action="store_true",
                            help="flush the pipeline before preparing "
                            "the experiment")
    parser_add.add_argument("-c", "--class-name", default=None,
                            help="name of the class to run")
    parser_add.add_argument("file",
                            help="file containing the experiment to run")
    parser_add.add_argument("arguments", nargs="*",
                            help="run arguments")

    parser_delete = subparsers.add_parser("delete",
                                          help="delete an experiment "
                                               "from the schedule")
    parser_delete.add_argument("rid", type=int,
                               help="run identifier (RID)")

    parser_set_device = subparsers.add_parser(
        "set-device", help="add or modify a device")
    parser_set_device.add_argument("name", help="name of the device")
    parser_set_device.add_argument("description",
                                   help="description in PYON format")

    parser_del_device = subparsers.add_parser(
        "del-device", help="delete a device")
    parser_del_device.add_argument("name", help="name of the device")

    parser_set_parameter = subparsers.add_parser(
        "set-parameter", help="add or modify a parameter")
    parser_set_parameter.add_argument("name", help="name of the parameter")
    parser_set_parameter.add_argument("value",
                                      help="value in PYON format")

    parser_del_parameter = subparsers.add_parser(
        "del-parameter", help="delete a parameter")
    parser_del_parameter.add_argument("name", help="name of the parameter")

    parser_show = subparsers.add_parser(
        "show", help="show schedule, devices or parameters")
    parser_show.add_argument(
        "what",
        help="select object to show: schedule/devices/parameters")

    parser_scan_repository = subparsers.add_parser(
        "scan-repository", help="rescan repository")

    return parser


def _parse_arguments(arguments):
    d = {}
    for argument in arguments:
        name, value = argument.split("=")
        d[name] = pyon.decode(value)
    return d


def _action_submit(remote, args):
    try:
        arguments = _parse_arguments(args.arguments)
    except:
        print("Failed to parse run arguments")
        sys.exit(1)

    expid = {
        "file": args.file,
        "class_name": args.class_name,
        "arguments": arguments,
    }
    if args.timed is None:
        due_date = None
    else:
        due_date = time.mktime(parse_date(args.timed).timetuple())
    rid = remote.submit(args.pipeline, expid,
                        args.priority, due_date, args.flush)
    print("RID: {}".format(rid))


def _action_delete(remote, args):
    remote.delete(args.rid)


def _action_set_device(remote, args):
    remote.set(args.name, pyon.decode(args.description))


def _action_del_device(remote, args):
    remote.delete(args.name)


def _action_set_parameter(remote, args):
    remote.set(args.name, pyon.decode(args.value))


def _action_del_parameter(remote, args):
    remote.delete(args.name)


def _action_scan_repository(remote, args):
    remote.scan_async()


def _show_schedule(schedule):
    clear_screen()
    if schedule:
        l = sorted(schedule.items(),
                   key=lambda x: (-x[1]["priority"],
                                  x[1]["due_date"] or 0,
                                  x[0]))
        table = PrettyTable(["RID", "Pipeline", "    Status    ", "Prio",
                             "Due date", "File", "Class name"])
        for rid, v in l:
            row = [rid, v["pipeline"], v["status"], v["priority"]]
            if v["due_date"] is None:
                row.append("")
            else:
                row.append(time.strftime("%m/%d %H:%M:%S",
                           time.localtime(v["due_date"])))
            row.append(v["expid"]["file"])
            if v["expid"]["class_name"] is None:
                row.append("")
            else:
                row.append(v["expid"]["class_name"])
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


def _show_parameters(parameters):
    clear_screen()
    table = PrettyTable(["Parameter", "Value"])
    for k, v in sorted(parameters.items(), key=itemgetter(0)):
        table.add_row([k, str(v)])
    print(table)


def _run_subscriber(host, port, subscriber):
    if port is None:
        port = 3250
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
    _run_subscriber(args.server, args.port, subscriber)


def main():
    args = get_argparser().parse_args()
    action = args.action.replace("-", "_")
    if action == "show":
        if args.what == "schedule":
            _show_dict(args, "schedule", _show_schedule)
        elif args.what == "devices":
            _show_dict(args, "devices", _show_devices)
        elif args.what == "parameters":
            _show_dict(args, "parameters", _show_parameters)
        else:
            print("Unknown object to show, use -h to list valid names.")
            sys.exit(1)
    else:
        port = 3251 if args.port is None else args.port
        target_name = {
            "submit": "master_schedule",
            "delete": "master_schedule",
            "set_device": "master_ddb",
            "del_device": "master_ddb",
            "set_parameter": "master_pdb",
            "del_parameter": "master_pdb",
            "scan_repository": "master_repository"
        }[action]
        remote = Client(args.server, port, target_name)
        try:
            globals()["_action_" + action](remote, args)
        finally:
            remote.close_rpc()

if __name__ == "__main__":
    main()
