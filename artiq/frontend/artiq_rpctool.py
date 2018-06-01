#!/usr/bin/env python3

import argparse
import textwrap
import sys
import traceback
import numpy as np  # Needed to use numpy in RPC call arguments on cmd line
import pprint
import inspect

from artiq.protocols.pc_rpc import AutoTarget, Client


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ RPC tool")
    parser.add_argument("server", metavar="SERVER",
                        help="hostname or IP of the controller to connect to")
    parser.add_argument("port", metavar="PORT", type=int,
                        help="TCP port to use to connect to the controller")
    subparsers = parser.add_subparsers(dest="action")
    subparsers.add_parser("list-targets", help="list existing targets")
    parser_list_methods = subparsers.add_parser("list-methods",
                                                help="list target's methods")
    parser_list_methods.add_argument("-t", "--target", help="target name")
    parser_call = subparsers.add_parser("call", help="call a target's method")
    parser_call.add_argument("-t", "--target", help="target name")
    parser_call.add_argument("method", metavar="METHOD", help="method name")
    parser_call.add_argument("args", metavar="ARGS", nargs=argparse.REMAINDER,
                             help="arguments")
    parser_interactive = subparsers.add_parser("interactive",
                                               help="enter interactive mode "
                                                    "(default)")
    parser_interactive.add_argument("-t", "--target", help="target name")
    return parser


def list_targets(target_names, description):
    print("Target(s):   " + ", ".join(target_names))
    if description is not None:
        print("Description: " + description)


def list_methods(remote):
    doc = remote.get_rpc_method_list()
    if doc["docstring"] is not None:
        print(doc["docstring"])
        print()
    for name, (argspec, docstring) in sorted(doc["methods"].items()):
        print(name + inspect.formatargspec(**argspec))
        if docstring is not None:
            print(textwrap.indent(docstring, "    "))
        print()


def call_method(remote, method_name, args):
    method = getattr(remote, method_name)
    ret = method(*[eval(arg) for arg in args])
    if ret is not None:
        pprint.pprint(ret)


def interactive(remote):
    try:
        import readline  # This makes input() nicer
    except ImportError:
        print("Warning: readline not available. "
              "Install it to add line editing capabilities.")

    while True:
        try:
            cmd = input("({}) ".format(remote.get_selected_target()))
        except EOFError:
            return
        class RemoteDict:
            def __getitem__(self, k):
                if k == "np":
                    return np
                else:
                    return getattr(remote, k)
        try:
            ret = eval(cmd, {}, RemoteDict())
        except Exception as e:
            if hasattr(e, "parent_traceback"):
                print("Remote exception:")
                print(traceback.format_exception_only(type(e), e)[0].rstrip())
                for l in e.parent_traceback:
                    print(l.rstrip())
            else:
                traceback.print_exc()
        else:
            if ret is not None:
                pprint.pprint(ret)


def main():
    args = get_argparser().parse_args()
    if not args.action:
        args.target = None

    remote = Client(args.server, args.port, None)
    targets, description = remote.get_rpc_id()
    if args.action != "list-targets":
        if not args.target:
            remote.select_rpc_target(AutoTarget)
        else:
            remote.select_rpc_target(args.target)

    if args.action == "list-targets":
        list_targets(targets, description)
    elif args.action == "list-methods":
        list_methods(remote)
    elif args.action == "call":
        call_method(remote, args.method, args.args)
    elif args.action == "interactive" or not args.action:
        interactive(remote)
    else:
        print("Unrecognized action: {}".format(args.action))

if __name__ == "__main__":
    main()
