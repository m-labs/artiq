#!/usr/bin/env python3

import argparse
import sys
import time
from operator import itemgetter
from itertools import chain
import logging

import h5py

from artiq.language.db import *
from artiq.language.experiment import is_experiment, Experiment
from artiq.protocols import pyon
from artiq.protocols.file_db import FlatFileDB
from artiq.master.worker_db import DBHub, ResultDB
from artiq.tools import file_import, verbosity_args, init_logger


logger = logging.getLogger(__name__)


class ELFRunner(Experiment, AutoDB):
    class DBKeys:
        comm = Device()
        file = Argument()

    def run(self):
        with open(self.file, "rb") as f:
            self.comm.load(f.read())
        self.comm.run("run")
        self.comm.serve(dict(), dict())


class SimpleParamLogger:
    def set(self, timestamp, name, value):
        logger.info("Parameter change: {} = {}".format(name, value))


class DummyWatchdog:
    def __init__(self, t):
        pass

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        pass


class DummyScheduler:
    def __init__(self):
        self.next_rid = 0
        self.next_trid = 0

    def run_queued(self, run_params):
        rid = self.next_rid
        self.next_rid += 1
        logger.info("Queuing: %s, RID=%s", run_params, rid)
        return rid

    def cancel_queued(self, rid):
        logger.info("Cancelling RID %s", rid)

    def run_timed(self, run_params, next_run):
        trid = self.next_trid
        self.next_trid += 1
        next_run_s = time.strftime("%m/%d %H:%M:%S", time.localtime(next_run))
        logger.info("Timing: %s at %s, TRID=%s", run_params, next_run_s, trid)
        return trid

    def cancel_timed(self, trid):
        logger.info("Cancelling TRID %s", trid)

    watchdog = DummyWatchdog


def get_argparser(with_file=True):
    parser = argparse.ArgumentParser(
        description="Local experiment running tool")

    verbosity_args(parser)
    parser.add_argument("-d", "--ddb", default="ddb.pyon",
                        help="device database file")
    parser.add_argument("-p", "--pdb", default="pdb.pyon",
                        help="parameter database file")

    parser.add_argument("-e", "--experiment", default=None,
                        help="experiment to run")
    parser.add_argument("-o", "--hdf5", default=None,
                        help="write results to specified HDF5 file"
                             " (default: print them)")
    if with_file:
        parser.add_argument("file",
                            help="file containing the experiment to run")
    parser.add_argument("arguments", nargs="*",
                        help="run arguments")

    return parser


def _parse_arguments(arguments):
    d = {}
    for argument in arguments:
        name, eq, value = argument.partition("=")
        d[name] = pyon.decode(value)
    return d


def _get_experiment(module, experiment=None):
    if experiment:
        return getattr(module, experiment)

    exps = [(k, v) for k, v in module.__dict__.items()
            if is_experiment(v)]
    if not exps:
        logger.error("No experiments in module")
    if len(exps) > 1:
        logger.warning("Multiple experiments (%s), using first",
                       ", ".join(k for (k, v) in exps))
    return exps[0][1]


def _build_experiment(dbh, args):
    if hasattr(args, "file"):
        if args.file.endswith(".elf"):
            if args.arguments:
                raise ValueError("arguments not supported for ELF kernels")
            if args.experiment:
                raise ValueError("experiment-by-name not supported "
                                 "for ELF kernels")
            return ELFRunner(dbh, file=args.file)
        else:
            module = file_import(args.file)
        file = args.file
    else:
        module = sys.modules["__main__"]
        file = getattr(module, "__file__")
    exp = _get_experiment(module, args.experiment)
    arguments = _parse_arguments(args.arguments)
    return exp(dbh,
               scheduler=DummyScheduler(),
               run_params=dict(file=file,
                               experiment=args.experiment,
                               arguments=arguments),
               **arguments)


def run(with_file=False):
    args = get_argparser(with_file).parse_args()
    init_logger(args)

    ddb = FlatFileDB(args.ddb)
    pdb = FlatFileDB(args.pdb)
    pdb.hooks.append(SimpleParamLogger())
    rdb = ResultDB(lambda description: None, lambda mod: None)
    dbh = DBHub(ddb, pdb, rdb)

    try:
        exp_inst = _build_experiment(dbh, args)
        rdb.build()
        exp_inst.run()
        exp_inst.analyze()
    finally:
        dbh.close_devices()

    if args.hdf5 is not None:
        with h5py.File(args.hdf5, "w") as f:
            rdb.write_hdf5(f)
    elif rdb.data.read or rdb.realtime_data.read:
        r = chain(rdb.realtime_data.read.items(), rdb.data.read.items())
        for k, v in sorted(r, key=itemgetter(0)):
            print("{}: {}".format(k, v))


def main():
    return run(with_file=True)


if __name__ == "__main__":
    main()
