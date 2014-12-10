#!/usr/bin/env python3

import argparse

from prettytable import PrettyTable

from artiq.management.pc_rpc import Client


def _get_args():
    parser = argparse.ArgumentParser(description="ARTIQ client")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port", default=8888, type=int,
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

    parser_show = subparsers.add_parser("show",
                                        help="show the experiment schedule")

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


def _action_show(remote, args):
    ce, queue = remote.get_schedule()
    if ce is None and not queue:
        print("Queue is empty")
    else:
        table = PrettyTable(["RID", "File", "Unit", "Function", "Timeout"])
        if ce is not None:
            rid, run_params, timeout, t = ce
            print("Currently executing RID {} for {:.1f}s".format(rid, t))
            row = [rid, run_params["file"]]
            for x in run_params["unit"], run_params["function"], timeout:
                row.append("-" if x is None else x)
            table.add_row(row)
        for rid, run_params, timeout in queue:
            row = [rid, run_params["file"]]
            for x in run_params["unit"], run_params["function"], timeout:
                row.append("-" if x is None else x)
            table.add_row(row)
        print("Run queue:")
        print(table)


def main():
    args = _get_args()
    remote = Client(args.server, args.port, "master")
    try:
        globals()["_action_" + args.action](remote, args)
    finally:
        remote.close_rpc()

if __name__ == "__main__":
    main()
