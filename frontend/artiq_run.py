#!/usr/bin/env python3

import argparse
import sys
from inspect import isclass
from operator import itemgetter

from artiq.management.file_import import file_import
from artiq.language.context import *
from artiq.management import pyon
from artiq.management.dpdb import DeviceParamDB


class ELFRunner(AutoContext):
    comm = Device("comm")
    implicit_core = False

    def run(self, filename, function):
        with open(filename, "rb") as f:
            binary = f.read()
        comm.load(binary)
        comm.run(function)
        comm.serve(dict(), dict())


def _get_args():
    parser = argparse.ArgumentParser(description="Experiment running tool")

    parser.add_argument("-d", "--ddb", default="ddb.pyon",
                        help="device database file")
    parser.add_argument("-p", "--pdb", default="pdb.pyon",
                        help="parameter database file")

    parser.add_argument("-e", "--elf", default=False, action="store_true",
                        help="run ELF binary")
    parser.add_argument("-f", "--function", default="run",
                        help="function to run")
    parser.add_argument("-u", "--unit", default=None,
                        help="unit to run")
    parser.add_argument("file",
                        help="file containing the unit to run")

    return parser.parse_args()


def main():
    args = _get_args()    

    devices = pyon.load_file(args.ddb)
    parameters = pyon.load_file(args.pdb)
    dpdb = DeviceParamDB(devices, parameters)
    try:
        if args.elf:
            unit_inst = ELFRunner(dpdb)
            unit_inst.run(args.file, args.function)
        else:
            module = file_import(args.file)
            if args.unit is None:
                units = [(k, v) for k, v in module.__dict__.items()
                         if k[0] != "_" and isclass(v) and issubclass(v, AutoContext) and v is not AutoContext]
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
            unit_inst = unit(dpdb)
            f = getattr(unit_inst, args.function)
            f()
    finally:
        dpdb.close()

if __name__ == "__main__":
    main()
