import os, sys

from pythonparser import diagnostic

from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import *

from artiq.compiler.module import Module
from artiq.compiler.embedding import Stitcher
from artiq.compiler.targets import OR1KTarget

# Import for side effects (creating the exception classes).
from artiq.coredevice import exceptions

def _render_diagnostic(diagnostic):
    def shorten_path(path):
        return path.replace(os.path.normpath(os.path.join(__file__, "..", "..")), "<artiq>")
    lines = [shorten_path(path) for path in diagnostic.render(colored=True)]
    return "\n".join(lines)

class _DiagnosticEngine(diagnostic.Engine):
    def render_diagnostic(self, diagnostic):
        sys.stderr.write(_render_diagnostic(diagnostic) + "\n")

class CompileError(Exception):
    def __init__(self, diagnostic):
        self.diagnostic = diagnostic

    def __str__(self):
        # Prepend a newline so that the message shows up on after
        # exception class name printed by Python.
        return "\n" + _render_diagnostic(self.diagnostic)


@syscall
def rtio_get_counter() -> TInt64:
    raise NotImplementedError("syscall not simulated")

@syscall
def cache_get(key: TStr) -> TList(TInt32):
    raise NotImplementedError("syscall not simulated")

@syscall
def cache_put(key: TStr, value: TList(TInt32)) -> TNone:
    raise NotImplementedError("syscall not simulated")

class Core:
    """Core device driver.

    :param ref_period: period of the reference clock for the RTIO subsystem.
        On platforms that use clock multiplication and SERDES-based PHYs,
        this is the period after multiplication. For example, with a RTIO core
        clocked at 125MHz and a SERDES multiplication factor of 8, the
        reference period is 1ns.
        The time machine unit is equal to this period.
    :param external_clock: whether the core device should switch to its
        external RTIO clock input instead of using its internal oscillator.
    :param comm_device: name of the device used for communications.
    """
    def __init__(self, dmgr, ref_period, external_clock=False, comm_device="comm"):
        self.ref_period = ref_period
        self.external_clock = external_clock
        self.comm = dmgr.get(comm_device)

        self.first_run = True
        self.core = self
        self.comm.core = self

    def compile(self, function, args, kwargs, set_result=None, with_attr_writeback=True):
        try:
            engine = _DiagnosticEngine(all_errors_are_fatal=True)

            stitcher = Stitcher(engine=engine)
            stitcher.stitch_call(function, args, kwargs, set_result)
            stitcher.finalize()

            module = Module(stitcher, ref_period=self.ref_period)
            target = OR1KTarget()

            library = target.compile_and_link([module])
            stripped_library = target.strip(library)

            return stitcher.object_map, stripped_library, \
                   lambda addresses: target.symbolize(library, addresses)
        except diagnostic.Error as error:
            raise CompileError(error.diagnostic) from error

    def run(self, function, args, kwargs):
        result = None
        def set_result(new_result):
            nonlocal result
            result = new_result

        object_map, kernel_library, symbolizer = self.compile(function, args, kwargs, set_result)

        if self.first_run:
            self.comm.check_ident()
            self.comm.switch_clock(self.external_clock)
            self.first_run = False

        self.comm.load(kernel_library)
        self.comm.run()
        self.comm.serve(object_map, symbolizer)

        return result

    @kernel
    def get_rtio_counter_mu(self):
        return rtio_get_counter()

    @kernel
    def break_realtime(self):
        """Set the timeline to the current value of the hardware RTIO counter
        plus a margin of 125000 machine units."""
        min_now = rtio_get_counter() + 125000
        if now_mu() < min_now:
            at_mu(min_now)

    @kernel
    def get_cache(self, key):
        return cache_get(key)

    @kernel
    def put_cache(self, key, value):
        return cache_put(key, value)
