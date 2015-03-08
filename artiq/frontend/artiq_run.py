#!/usr/bin/env python3

import argparse
import sys
import time
from operator import itemgetter
from itertools import chain

import h5py

from artiq.language.db import *
from artiq.language.experiment import is_experiment
from artiq.protocols import pyon
from artiq.protocols.file_db import FlatFileDB
from artiq.master.worker_db import DBHub, ResultDB
from artiq.tools import file_import, verbosity_args, init_logger


class ELFRunner(AutoDB):
    class DBKeys:
        comm = Device()

    def run(self, filename):
        with open(filename, "rb") as f:
            binary = f.read()
        comm.load(binary)
        comm.run("run")
        comm.serve(dict(), dict())


class SimpleParamLogger:
    def set(self, timestamp, name, value):
        print("Parameter change: {} -> {}".format(name, value))


class DummyScheduler:
    def __init__(self):
        self.next_rid = 0
        self.next_trid = 0

    def run_queued(self, run_params):
        rid = self.next_rid
        self.next_rid += 1
        print("Queuing: {}, RID={}".format(run_params, rid))
        return rid

    def cancel_queued(self, rid):
        print("Cancelling RID {}".format(rid))

    def run_timed(self, run_params, next_run):
        trid = self.next_trid
        self.next_trid += 1
        next_run_s = time.strftime("%m/%d %H:%M:%S", time.localtime(next_run))
        print("Timing: {} at {}, TRID={}".format(run_params, next_run_s, trid))
        return trid

    def cancel_timed(self, trid):
        print("Cancelling TRID {}".format(trid))


def get_argparser():
    parser = argparse.ArgumentParser(
        description="Local experiment running tool")

    verbosity_args(parser)
    parser.add_argument("-d", "--ddb", default="ddb.pyon",
                        help="device database file")
    parser.add_argument("-p", "--pdb", default="pdb.pyon",
                        help="parameter database file")

    parser.add_argument("-E", "--elf", default=False, action="store_true",
                        help="run ELF binary")
    parser.add_argument("-e", "--experiment", default=None,
                        help="experiment to run")
    parser.add_argument("-o", "--hdf5", default=None,
                        help="write results to specified HDF5 file"
                             " (default: print them)")
    parser.add_argument("file",
                        help="file containing the experiment to run")
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
    rdb = ResultDB(lambda description: None, lambda mod: None)
    dbh = DBHub(ddb, pdb, rdb)
    try:
        if args.elf:
            if args.arguments:
                print("Run arguments are not supported in ELF mode")
                sys.exit(1)
            exp_inst = ELFRunner(dps)
            exp_inst.run(args.file)
        else:
            module = file_import(args.file)
            if args.experiment is None:
                exps = [(k, v) for k, v in module.__dict__.items()
                        if is_experiment(v)]
                l = len(exps)
                if l == 0:
                    print("No experiments found in module")
                    sys.exit(1)
                elif l > 1:
                    print("More than one experiment found in module:")
                    for k, v in sorted(experiments, key=itemgetter(0)):
                        if v.__doc__ is None:
                            print("    {}".format(k))
                        else:
                            print("    {} ({})".format(
                                k, v.__doc__.splitlines()[0].strip()))
                    print("Use -u to specify which experiment to use.")
                    sys.exit(1)
                else:
                    exp = exps[0][1]
            else:
                exp = getattr(module, args.experiment)

            try:
                arguments = _parse_arguments(args.arguments)
            except:
                print("Failed to parse run arguments")
                sys.exit(1)

            run_params = {
                "file": args.file,
                "experiment": args.experiment,
                "timeout": None,
                "arguments": arguments
            }
            exp_inst = exp(dbh,
                           scheduler=DummyScheduler(),
                           run_params=run_params,
                           **run_params["arguments"])
            exp_inst.run()
            exp_inst.analyze()

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
