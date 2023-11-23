#!/usr/bin/env python3

import os, sys, io, tarfile, logging, argparse

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
    parser.add_argument("--dataset-db", default="dataset_db.mdb",
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
    dataset_db = DatasetDB(args.dataset_db)
    try:
        dataset_mgr = DatasetManager(dataset_db)

        try:
            module = file_import(args.file, prefix="artiq_run_")
            exp = get_experiment(module, args.class_name)
            arguments = parse_arguments(args.arguments)
            argument_mgr = ProcessArgumentManager(arguments)
            exp_inst = exp((device_mgr, dataset_mgr, argument_mgr, {}))
            argument_mgr.check_unprocessed_arguments()


            if not hasattr(exp.run, "artiq_embedded"):
                raise ValueError("Experiment entry point must be a kernel")
            core_name = exp.run.artiq_embedded.core_name
            core = getattr(exp_inst, core_name)

            object_map, main_kernel_library, _, _, subkernel_arg_types = \
                core.compile(exp.run, [exp_inst], {},
                             attribute_writeback=False, print_as_rpc=False)

            subkernels = object_map.subkernels()
            compiled_subkernels = {}
            while True:
                new_subkernels = {}
                for sid, subkernel_fn in subkernels.items():
                    if sid in compiled_subkernels.keys():
                        continue
                    destination, subkernel_library, embedding_map = core.compile_subkernel(
                        sid, subkernel_fn, object_map, 
                        [exp_inst], subkernel_arg_types, subkernels)
                    compiled_subkernels[sid] = (destination, subkernel_library)
                    new_subkernels.update(embedding_map.subkernels())
                if new_subkernels == subkernels:
                    break
                subkernels.update(new_subkernels)
        except CompileError as error:
            return
        finally:
            device_mgr.close_devices()
    finally:
        dataset_db.close_db()

    if object_map.has_rpc():
        raise ValueError("Experiment must not use RPC")

    output = args.output

    if not subkernels:
        # just write the ELF file
        if output is None:
            basename, ext = os.path.splitext(args.file)
            output = "{}.elf".format(basename)

        with open(output, "wb") as f:
            f.write(main_kernel_library)
    else:
        # combine them in a tar archive
        if output is None:
            basename, ext = os.path.splitext(args.file)
            output = "{}.tar".format(basename)

        with tarfile.open(output, "w:") as tar:
            # write the main lib as "main.elf"
            main_kernel_fileobj = io.BytesIO(main_kernel_library)
            main_kernel_info = tarfile.TarInfo(name="main.elf")
            main_kernel_info.size = len(main_kernel_library)
            tar.addfile(main_kernel_info, fileobj=main_kernel_fileobj)

            # subkernels as "<sid> <destination>.elf"
            for sid, (destination, subkernel_library) in compiled_subkernels.items():
                subkernel_fileobj = io.BytesIO(subkernel_library)
                subkernel_info = tarfile.TarInfo(name="{} {}.elf".format(sid, destination))
                subkernel_info.size = len(subkernel_library)
                tar.addfile(subkernel_info, fileobj=subkernel_fileobj)


if __name__ == "__main__":
    main()
