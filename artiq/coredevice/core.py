import os, sys, tempfile

from pythonparser import diagnostic

from artiq.language.core import *
from artiq.language.units import ns

from artiq.compiler import Stitcher, Module
from artiq.compiler.targets import OR1KTarget

# Import for side effects (creating the exception classes).
from artiq.coredevice import exceptions


class CompileError(Exception):
    pass

class Core:
    def __init__(self, dmgr, ref_period=8*ns, external_clock=False):
        self.comm = dmgr.get("comm")
        self.ref_period = ref_period
        self.external_clock = external_clock

        self.first_run = True
        self.core = self
        self.comm.core = self

    def compile(self, function, args, kwargs, with_attr_writeback=True):
        try:
            engine = diagnostic.Engine(all_errors_are_fatal=True)

            stitcher = Stitcher(engine=engine)
            stitcher.stitch_call(function, args, kwargs)

            module = Module(stitcher)
            target = OR1KTarget()

            if os.getenv('ARTIQ_DUMP_IR'):
                print("====== ARTIQ IR DUMP ======", file=sys.stderr)
                for function in module.artiq_ir:
                    print(function, file=sys.stderr)

            if os.getenv('ARTIQ_DUMP_LLVM'):
                print("====== LLVM IR DUMP ======", file=sys.stderr)
                print(module.build_llvm_ir(target), file=sys.stderr)

            return target.compile_and_link([module]), stitcher.rpc_map
        except diagnostic.Error as error:
            print("\n".join(error.diagnostic.render(colored=True)), file=sys.stderr)
            raise CompileError() from error

    def run(self, function, args, kwargs):
        kernel_library, rpc_map = self.compile(function, args, kwargs)

        if self.first_run:
            self.comm.check_ident()
            self.comm.switch_clock(self.external_clock)
            self.first_run = False

        try:
            self.comm.load(kernel_library)
        except Exception as error:
            shlib_temp = tempfile.NamedTemporaryFile(suffix=".so", delete=False)
            shlib_temp.write(kernel_library)
            shlib_temp.close()
            raise RuntimeError("shared library dumped to {}".format(shlib_temp.name)) from error

        self.comm.run()
        self.comm.serve(rpc_map)

    @kernel
    def get_rtio_counter_mu(self):
        return syscall("rtio_get_counter")

    @kernel
    def break_realtime(self):
        at_mu(syscall("rtio_get_counter") + 125000)
