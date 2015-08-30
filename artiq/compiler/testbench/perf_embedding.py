import sys, os
from pythonparser import diagnostic
from ...protocols.file_db import FlatFileDB
from ...master.worker_db import DeviceManager
from .. import Module
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

    with open(sys.argv[1]) as f:
        testcase_code = compile(f.read(), f.name, "exec")
        testcase_vars = {'__name__': 'testbench'}
        exec(testcase_code, testcase_vars)

    ddb_path = os.path.join(os.path.dirname(sys.argv[1]), "ddb.pyon")
    dmgr = DeviceManager(FlatFileDB(ddb_path))

    def embed():
        experiment = testcase_vars["Benchmark"](dmgr)

        stitcher = Stitcher()
        stitcher.stitch_call(experiment.run, (experiment,), {})
        stitcher.finalize()
        return stitcher

    stitcher = embed()
    module = Module(stitcher)

    benchmark(lambda: embed(),
              "ARTIQ embedding")

    benchmark(lambda: Module(stitcher),
              "ARTIQ transforms and validators")

    benchmark(lambda: OR1KTarget().compile_and_link([module]),
              "LLVM optimization and linking")

if __name__ == "__main__":
    main()
