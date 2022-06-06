#!/usr/bin/env python3
# Copyright (C) 2014, 2015 M-Labs Limited
# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import argparse
import sys
from operator import itemgetter
import logging
from collections import defaultdict

import h5py

from sipyco import common_args

from artiq import __version__ as artiq_version
from artiq.language.environment import EnvExperiment, ProcessArgumentManager
from artiq.master.databases import DeviceDB, DatasetDB
from artiq.master.worker_db import DeviceManager, DatasetManager
from artiq.language import import_cache
from artiq.tools import *


logger = logging.getLogger(__name__)


class FileRunner(EnvExperiment):
    def build(self, file):
        self.setattr_device("core")
        self.file = file

    def run(self):
        kernel_library = self.compile()

        self.core.comm.load(kernel_library)
        self.core.comm.run()
        self.core.comm.serve(None, None)


class ELFRunner(FileRunner):
    def compile(self):
        with open(self.file, "rb") as f:
            return f.read()


class DummyScheduler:
    def __init__(self):
        self.rid = 0
        self.pipeline_name = "main"
        self.priority = 0
        self.expid = None

        self._next_rid = 1

    def submit(self, pipeline_name=None, expid=None, priority=None, due_date=None, flush=False):
        rid = self._next_rid
        self._next_rid += 1
        logger.info("Submitting: %s, RID=%s", expid, rid)
        return rid

    def delete(self, rid):
        logger.info("Deleting RID %s", rid)

    def request_termination(self, rid):
        logger.info("Requesting termination of RID %s", rid)

    def get_status(self):
        return dict()

    def check_pause(self, rid=None) -> bool:
        return False

    def pause(self):
        pass


class DummyCCB:
    def issue(self, service, *args, **kwargs):
        logger.info("CCB for service '%s' (args %s, kwargs %s)",
                    service, args, kwargs)


def get_argparser(with_file=True):
    parser = argparse.ArgumentParser(
        description="Local experiment running tool")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    common_args.verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                        help="device database file (default: '%(default)s')")
    parser.add_argument("--dataset-db", default="dataset_db.pyon",
                        help="dataset file (default: '%(default)s')")

    parser.add_argument("-c", "--class-name", default=None,
                        help="name of the class to run")
    parser.add_argument("-o", "--hdf5", default=None,
                        help="write results to specified HDF5 file"
                             " (default: print them)")
    if with_file:
        parser.add_argument("file", metavar="FILE",
                            help="file containing the experiment to run")
    parser.add_argument("arguments", metavar="ARGUMENTS", nargs="*",
                        help="run arguments")

    return parser


def _build_experiment(device_mgr, dataset_mgr, args):
    arguments = parse_arguments(args.arguments)
    argument_mgr = ProcessArgumentManager(arguments)
    managers = (device_mgr, dataset_mgr, argument_mgr, {})
    if hasattr(args, "file"):
        is_elf = args.file.endswith(".elf")
        if is_elf:
            if args.arguments:
                raise ValueError("arguments not supported for precompiled kernels")
            if args.class_name:
                raise ValueError("class-name not supported "
                                 "for precompiled kernels")
        if is_elf:
            return ELFRunner(managers, file=args.file)
        else:
            import_cache.install_hook()
            module = file_import(args.file, prefix="artiq_run_")
        file = args.file
    else:
        module = sys.modules["__main__"]
        file = getattr(module, "__file__")
    expid = {
        "file": file,
        "class_name": args.class_name,
        "arguments": arguments
    }
    device_mgr.virtual_devices["scheduler"].expid = expid
    return get_experiment(module, args.class_name)(managers)


def run(with_file=False):
    args = get_argparser(with_file).parse_args()
    common_args.init_logger_from_args(args)

    device_mgr = DeviceManager(DeviceDB(args.device_db),
                               virtual_devices={"scheduler": DummyScheduler(),
                                                "ccb": DummyCCB()})
    dataset_db = DatasetDB(args.dataset_db)
    dataset_mgr = DatasetManager(dataset_db)

    try:
        exp_inst = _build_experiment(device_mgr, dataset_mgr, args)
        exp_inst.prepare()
        exp_inst.run()
        exp_inst.analyze()
    except Exception as exn:
        if hasattr(exn, "artiq_core_exception"):
            print(exn.artiq_core_exception, file=sys.stderr)
        raise exn
    finally:
        device_mgr.close_devices()

    if args.hdf5 is not None:
        with h5py.File(args.hdf5, "w") as f:
            dataset_mgr.write_hdf5(f)
    else:
        for k, v in sorted(dataset_mgr.local.items(), key=itemgetter(0)):
            print("{}: {}".format(k, v))
    dataset_db.save()


def main():
    return run(with_file=True)


if __name__ == "__main__":
    main()
