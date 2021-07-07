#!/usr/bin/env python3

import os, sys, logging, argparse

from sipyco import common_args

from artiq import __version__ as artiq_version
from artiq.master.databases import DeviceDB, DatasetDB
from artiq.master.worker_db import DeviceManager, DatasetManager
from artiq.language.environment import ProcessArgumentManager
from artiq.coredevice.core import CompileError
from artiq.tools import *


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ static compiler")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    common_args.verbosity_args(parser)
    parser.add_argument("--device-db", default="device_db.py",
                        help="device database file (default: '%(default)s')")
    parser.add_argument("--dataset-db", default="dataset_db.pyon",
                        help="dataset file (default: '%(default)s')")

    parser.add_argument("-c", "--class-name", default=None,
                        help="name of the class to compile")

    parser.add_argument("-o", "--output", default=None,
                        help="output file")
    parser.add_argument("file", metavar="FILE",
                        help="file containing the experiment to compile")
    parser.add_argument("arguments", metavar="ARGUMENTS",
                        nargs="*", help="run arguments")

    return parser


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    device_mgr = DeviceManager(DeviceDB(args.device_db))
    dataset_mgr = DatasetManager(DatasetDB(args.dataset_db))

    try:
        module = file_import(args.file, prefix="artiq_run_")
        exp = get_experiment(module, args.class_name)
        arguments = parse_arguments(args.arguments)
        argument_mgr = ProcessArgumentManager(arguments)
        exp_inst = exp((device_mgr, dataset_mgr, argument_mgr, {}))

        if not hasattr(exp.run, "artiq_embedded"):
            raise ValueError("Experiment entry point must be a kernel")
        core_name = exp.run.artiq_embedded.core_name
        core = getattr(exp_inst, core_name)

        object_map, kernel_library, _, _ = \
            core.compile(exp.run, [exp_inst], {},
                         attribute_writeback=False, print_as_rpc=False)
    except CompileError as error:
        return
    finally:
        device_mgr.close_devices()

    if object_map.has_rpc():
        raise ValueError("Experiment must not use RPC")

    output = args.output
    if output is None:
        basename, ext = os.path.splitext(args.file)
        output = "{}.elf".format(basename)

    with open(output, "wb") as f:
        f.write(kernel_library)

if __name__ == "__main__":
    main()
