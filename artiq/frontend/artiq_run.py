#!/usr/bin/env python3

import argparse
import sys
from inspect import isclass
from operator import itemgetter
from itertools import chain

import h5py

from artiq.language.db import *
from artiq.protocols import pyon
from artiq.protocols.file_db import FlatFileDB
from artiq.master.db import DBHub, ResultDB
from artiq.tools import file_import, verbosity_args, init_logger


class ELFRunner(AutoDB):
    class DBKeys:
        comm = Device()
        implicit_core = False

    def run(self, filename):
        with open(filename, "rb") as f:
            binary = f.read()
        comm.load(binary)
        comm.run("run")
        comm.serve(dict(), dict())


class SimpleParamLogger:
    def set(self, timestamp, name, value):
        print("Parameter change: {} -> {}".format(name, value))


def get_argparser():
    parser = argparse.ArgumentParser(
        description="Local experiment running tool")

    verbosity_args(parser)
    parser.add_argument("-d", "--ddb", default="ddb.pyon",
                        help="device database file")
    parser.add_argument("-p", "--pdb", default="pdb.pyon",
                        help="parameter database file")

    parser.add_argument("-e", "--elf", default=False, action="store_true",
                        help="run ELF binary")
    parser.add_argument("-u", "--unit", default=None,
                        help="unit to run")
    parser.add_argument("-o", "--hdf5", default=None,
                        help="write results to specified HDF5 file"
                             " (default: print them)")
    parser.add_argument("file",
                        help="file containing the unit to run")
    parser.add_argument("arguments", nargs="*",
                        help="run arguments")

    return parser


def _parse_arguments(arguments):
    d = {}
    for argument in arguments:
        name, value = argument.split("=")
        d[name] = pyon.decode(value)
    return d


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    ddb = FlatFileDB(args.ddb)
    pdb = FlatFileDB(args.pdb)
    pdb.hooks.append(SimpleParamLogger())
    rdb = ResultDB(set())
    dbh = DBHub(ddb, pdb, rdb)
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
                            and issubclass(v, AutoDB)
                            and v is not AutoDB]
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

            unit_inst = unit(dbh, **arguments)
            unit_inst.run()
            if hasattr(unit_inst, "analyze"):
                unit_inst.analyze()

            if args.hdf5 is not None:
                f = h5py.File(args.hdf5, "w")
                try:
                    rdb.write_hdf5(f)
                finally:
                    f.close()
            else:
                if rdb.data.read or rdb.realtime_data.read:
                    print("Results:")
                    for k, v in sorted(chain(rdb.realtime_data.read.items(),
                                             rdb.data.read.items()),
                                       key=itemgetter(0)):
                        print("{}: {}".format(k, v))
    finally:
        dbh.close()

if __name__ == "__main__":
    main()
