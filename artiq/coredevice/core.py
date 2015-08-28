import sys

from pythonparser import diagnostic

from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import *

from artiq.compiler import Stitcher, Module
from artiq.compiler.targets import OR1KTarget

# Import for side effects (creating the exception classes).
from artiq.coredevice import exceptions


class CompileError(Exception):
    pass


@syscall
def rtio_get_counter() -> TInt64:
    raise NotImplementedError("syscall not simulated")

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
            stitcher.finalize()

            module = Module(stitcher)
            target = OR1KTarget()

            library = target.compile_and_link([module])
            stripped_library = target.strip(library)

            return stitcher.object_map, stripped_library, \
                   lambda addresses: target.symbolize(library, addresses)
        except diagnostic.Error as error:
            raise CompileError() from error

    def run(self, function, args, kwargs):
        object_map, kernel_library, symbolizer = self.compile(function, args, kwargs)

        if self.first_run:
            self.comm.check_ident()
            self.comm.switch_clock(self.external_clock)
            self.first_run = False

        self.comm.load(kernel_library)
        self.comm.run()
        self.comm.serve(object_map, symbolizer)

    @kernel
    def get_rtio_counter_mu(self):
        return rtio_get_counter()

    @kernel
    def break_realtime(self):
        at_mu(rtio_get_counter() + 125000)
