#!/usr/bin/env python3

import logging
import argparse

from artiq.protocols.file_db import FlatFileDB
from artiq.master.worker_db import DeviceManager
from artiq.tools import *


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ static compiler")

    verbosity_args(parser)
    parser.add_argument("-d", "--ddb", default="ddb.pyon",
                        help="device database file")
    parser.add_argument("-p", "--pdb", default="pdb.pyon",
                        help="parameter database file")

    parser.add_argument("-e", "--experiment", default=None,
                        help="experiment to compile")

    parser.add_argument("-o", "--output", default=None,
                        help="output file")
    parser.add_argument("file",
                        help="file containing the experiment to compile")
    parser.add_argument("arguments", nargs="*", help="run arguments")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dmgr = DeviceManager(FlatFileDB(args.ddb))
    pdb = FlatFileDB(args.pdb)

    try:
        module = file_import(args.file)
        exp = get_experiment(module, args.experiment)
        arguments = parse_arguments(args.arguments)
        exp_inst = exp(dmgr, pdb, **arguments)

        if (not hasattr(exp.run, "k_function_info")
                or not exp.run.k_function_info):
            raise ValueError("Experiment entry point must be a kernel")
        core_name = exp.run.k_function_info.core_name
        core = getattr(exp_inst, core_name)

        binary, rpc_map, _ = core.compile(exp.run.k_function_info.k_function,
                                          [exp_inst], {},
                                          with_attr_writeback=False)
    finally:
        dmgr.close_devices()

    if rpc_map:
        raise ValueError("Experiment must not use RPC")

    output = args.output
    if output is None:
        output = args.file
        if output.endswith(".py"):
            output = output[:-3]
        output += ".elf"
    with open(output, "wb") as f:
        f.write(binary)

if __name__ == "__main__":
    main()
