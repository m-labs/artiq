import sys, os, tokenize
from pythonparser import diagnostic
from ...language.environment import ProcessArgumentManager
from ...master.databases import DeviceDB, DatasetDB
from ...master.worker_db import DeviceManager, DatasetManager
from ..module import Module
from ..embedding import Stitcher
from ..targets import OR1KTarget
from . import benchmark


def main():
    if not len(sys.argv) == 2:
        print("Expected exactly one module filename", file=sys.stderr)
        exit(1)

    def process_diagnostic(diag):
        print("\n".join(diag.render()), file=sys.stderr)
        if diag.level in ("fatal", "error"):
            exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    with tokenize.open(sys.argv[1]) as f:
        testcase_code = compile(f.read(), f.name, "exec")
        testcase_vars = {'__name__': 'testbench'}
        exec(testcase_code, testcase_vars)

    device_db_path = os.path.join(os.path.dirname(sys.argv[1]), "device_db.py")
    device_mgr = DeviceManager(DeviceDB(device_db_path))

    dataset_db_path = os.path.join(os.path.dirname(sys.argv[1]), "dataset_db.pyon")
    dataset_mgr = DatasetManager(DatasetDB(dataset_db_path))

    argument_mgr = ProcessArgumentManager({})

    def embed():
        experiment = testcase_vars["Benchmark"]((device_mgr, dataset_mgr, argument_mgr))

        stitcher = Stitcher(core=experiment.core, dmgr=device_mgr)
        stitcher.stitch_call(experiment.run, (), {})
        stitcher.finalize()
        return stitcher

    stitcher = embed()
    module = Module(stitcher)
    target = OR1KTarget()
    llvm_ir = target.compile(module)
    elf_obj = target.assemble(llvm_ir)
    elf_shlib = target.link([elf_obj])

    benchmark(lambda: embed(),
              "ARTIQ embedding")

    benchmark(lambda: Module(stitcher),
              "ARTIQ transforms and validators")

    benchmark(lambda: target.compile(module),
              "LLVM optimizations")

    benchmark(lambda: target.assemble(llvm_ir),
              "LLVM machine code emission")

    benchmark(lambda: target.link([elf_obj]),
              "Linking")

    benchmark(lambda: target.strip(elf_shlib),
              "Stripping debug information")

if __name__ == "__main__":
    main()
