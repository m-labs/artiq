#!/usr/bin/env python3

import argparse
import sys
from inspect import isclass
from operator import itemgetter

from artiq.management.file_import import file_import
from artiq.language.context import *
from artiq.management import pyon
from artiq.management.dpdb import DeviceParamDB, DeviceParamSupplier


class ELFRunner(AutoContext):
    comm = Device("comm")
    implicit_core = False

    def run(self, filename):
        with open(filename, "rb") as f:
            binary = f.read()
        comm.load(binary)
        comm.run("run")
        comm.serve(dict(), dict())


def _get_args():
    parser = argparse.ArgumentParser(description="Local running tool")

    parser.add_argument("-d", "--ddb", default="ddb.pyon",
                        help="device database file")
    parser.add_argument("-p", "--pdb", default="pdb.pyon",
                        help="parameter database file")

    parser.add_argument("-e", "--elf", default=False, action="store_true",
                        help="run ELF binary")
    parser.add_argument("-u", "--unit", default=None,
                        help="unit to run")
    parser.add_argument("file",
                        help="file containing the unit to run")
    parser.add_argument("arguments", nargs="*",
                        help="run arguments")

    return parser.parse_args()


def _parse_arguments(arguments):
    d = {}
    for argument in arguments:
        name, value = argument.split("=")
        d[name] = pyon.decode(value)
    return d


def main():
    args = _get_args()

    dpdb = DeviceParamDB(args.ddb, args.pdb)
    dps = DeviceParamSupplier(dpdb.req_device, dpdb.req_parameter)
    try:
        if args.elf:
            if args.arguments:
                print("Run arguments are not supported in ELF mode")
                sys.exit(1)
            unit_inst = ELFRunner(dps)
            unit_inst.run(args.file)
        else:
            module = file_import(args.file)
            if args.unit is None:
                units = [(k, v) for k, v in module.__dict__.items()
                         if k[0] != "_"
                            and isclass(v)
                            and issubclass(v, AutoContext)
                            and v is not AutoContext]
                l = len(units)
                if l == 0:
                    print("No units found in module")
                    sys.exit(1)
                elif l > 1:
                    print("More than one unit found in module:")
                    for k, v in sorted(units, key=itemgetter(0)):
                        print("    " + k)
                    print("Use -u to specify which unit to use.")
                    sys.exit(1)
                else:
                    unit = units[0][1]
            else:
                unit = getattr(module, args.unit)

            try:
                arguments = _parse_arguments(args.arguments)
            except:
                print("Failed to parse run arguments")
                sys.exit(1)

            unit_inst = unit(dps)
            unit_inst.run(**arguments)

            if dps.parameter_wb:
                print("Modified parameters:")
                for requester, name in dps.parameter_wb:
                    print("{}: {}".format(name, getattr(requester, name)))
    finally:
        dps.close()

if __name__ == "__main__":
    main()
