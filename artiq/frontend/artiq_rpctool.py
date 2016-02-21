#!/usr/bin/env python3.5

import argparse
import textwrap
import sys
import numpy as np  # Needed to use numpy in RPC call arguments on cmd line
import pprint

from artiq.protocols.pc_rpc import AutoTarget, Client


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ RPC tool")
    parser.add_argument("server",
                        help="hostname or IP of the controller to connect to")
    parser.add_argument("port", type=int,
                        help="TCP port to use to connect to the controller")
    subparsers = parser.add_subparsers(dest="action")
    subparsers.required = True
    subparsers.add_parser("list-targets", help="list existing targets")
    parser_list_methods = subparsers.add_parser("list-methods",
                                                help="list target's methods")
    parser_list_methods.add_argument("-t", "--target", help="target name")
    parser_call = subparsers.add_parser("call", help="call a target's method")
    parser_call.add_argument("-t", "--target", help="target name")
    parser_call.add_argument("method", help="method name")
    parser_call.add_argument("args", nargs=argparse.REMAINDER,
                             help="arguments")
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
        args = ""
        for arg in argspec["args"]:
            args += arg
            if argspec["defaults"] is not None:
                kword_index = len(argspec["defaults"]) - len(argspec["args"])\
                    + argspec["args"].index(arg)
                if kword_index >= 0:
                    if argspec["defaults"][kword_index] == Ellipsis:
                        args += "=..."
                    else:
                        args += "={}".format(argspec["defaults"][kword_index])
            if argspec["args"].index(arg) < len(argspec["args"]) - 1:
                args += ", "
        if argspec["varargs"] is not None:
            args += ", *{}".format(argspec["varargs"])
        elif len(argspec["kwonlyargs"]) > 0:
                args += ", *"
        for kwonlyarg in argspec["kwonlyargs"]:
            args += ", {}".format(kwonlyarg)
            if kwonlyarg in argspec["kwonlydefaults"]:
                if argspec["kwonlydefaults"][kwonlyarg] == Ellipsis:
                    args += "=..."
                else:
                    args += "={}".format(argspec["kwonlydefaults"][kwonlyarg])
        if argspec["varkw"] is not None:
            args += ", **{}".format(argspec["varkw"])
        print("{}({})".format(name, args))
        if docstring is not None:
            print(textwrap.indent(docstring, "    "))
        print()


def call_method(remote, method_name, args):
    method = getattr(remote, method_name)
    ret = method(*[eval(arg) for arg in args])
    if ret is not None:
        pprint.pprint(ret)


def main():
    args = get_argparser().parse_args()

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
    else:
        print("Unrecognized action: {}".format(args.action))

if __name__ == "__main__":
    main()
