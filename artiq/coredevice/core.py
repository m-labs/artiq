import os, sys
import numpy

from pythonparser import diagnostic

from artiq import __artiq_dir__ as artiq_dir

from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import *

from artiq.compiler.module import Module
from artiq.compiler.embedding import Stitcher
from artiq.compiler.targets import OR1KTarget

from artiq.coredevice.comm_kernel import CommKernel, CommKernelDummy
# Import for side effects (creating the exception classes).
from artiq.coredevice import exceptions


def _render_diagnostic(diagnostic, colored):
    def shorten_path(path):
        return path.replace(artiq_dir, "<artiq>")
    lines = [shorten_path(path) for path in diagnostic.render(colored=colored)]
    return "\n".join(lines)

colors_supported = os.name == "posix"
class _DiagnosticEngine(diagnostic.Engine):
    def render_diagnostic(self, diagnostic):
        sys.stderr.write(_render_diagnostic(diagnostic, colored=colors_supported) + "\n")

class CompileError(Exception):
    def __init__(self, diagnostic):
        self.diagnostic = diagnostic

    def __str__(self):
        # Prepend a newline so that the message shows up on after
        # exception class name printed by Python.
        return "\n" + _render_diagnostic(self.diagnostic, colored=colors_supported)


@syscall
def rtio_init() -> TNone:
    raise NotImplementedError("syscall not simulated")

@syscall(flags={"nounwind", "nowrite"})
def rtio_get_counter() -> TInt64:
    raise NotImplementedError("syscall not simulated")

@syscall(flags={"nounwind", "nowrite"})
def drtio_get_link_status(linkno: TInt32) -> TBool:
    raise NotImplementedError("syscall not simulated")


class Core:
    """Core device driver.

    :param host: hostname or IP address of the core device.
    :param ref_period: period of the reference clock for the RTIO subsystem.
        On platforms that use clock multiplication and SERDES-based PHYs,
        this is the period after multiplication. For example, with a RTIO core
        clocked at 125MHz and a SERDES multiplication factor of 8, the
        reference period is 1ns.
        The time machine unit is equal to this period.
    :param external_clock: whether the core device should switch to its
        external RTIO clock input instead of using its internal oscillator.
    :param ref_multiplier: ratio between the RTIO fine timestamp frequency
        and the RTIO coarse timestamp frequency (e.g. SERDES multiplication
        factor).
    """

    kernel_invariants = {
        "core", "ref_period", "coarse_ref_period", "ref_multiplier",
        "external_clock",
    }

    def __init__(self, dmgr, host, ref_period, external_clock=False,
                 ref_multiplier=8):
        self.ref_period = ref_period
        self.external_clock = external_clock
        self.ref_multiplier = ref_multiplier
        self.coarse_ref_period = ref_period*ref_multiplier
        if host is None:
            self.comm = CommKernelDummy()
        else:
            self.comm = CommKernel(host)

        self.first_run = True
        self.dmgr = dmgr
        self.core = self
        self.comm.core = self

    def close(self):
        self.comm.close()

    def compile(self, function, args, kwargs, set_result=None,
                attribute_writeback=True, print_as_rpc=True):
        try:
            engine = _DiagnosticEngine(all_errors_are_fatal=True)

            stitcher = Stitcher(engine=engine, core=self, dmgr=self.dmgr,
                                print_as_rpc=print_as_rpc)
            stitcher.stitch_call(function, args, kwargs, set_result)
            stitcher.finalize()

            module = Module(stitcher,
                ref_period=self.ref_period,
                attribute_writeback=attribute_writeback)
            target = OR1KTarget()

            library = target.compile_and_link([module])
            stripped_library = target.strip(library)

            return stitcher.embedding_map, stripped_library, \
                   lambda addresses: target.symbolize(library, addresses), \
                   lambda symbols: target.demangle(symbols)
        except diagnostic.Error as error:
            raise CompileError(error.diagnostic) from error

    def run(self, function, args, kwargs):
        result = None
        @rpc(flags={"async"})
        def set_result(new_result):
            nonlocal result
            result = new_result

        embedding_map, kernel_library, symbolizer, demangler = \
            self.compile(function, args, kwargs, set_result)

        if self.first_run:
            self.comm.check_system_info()
            self.comm.switch_clock(self.external_clock)
            self.first_run = False

        self.comm.load(kernel_library)
        self.comm.run()
        self.comm.serve(embedding_map, symbolizer, demangler)

        return result

    @portable
    def seconds_to_mu(self, seconds):
        """Converts seconds to the corresponding number of machine units
        (RTIO cycles).

        :param seconds: time (in seconds) to convert.
        """
        return numpy.int64(seconds//self.ref_period)

    @portable
    def mu_to_seconds(self, mu):
        """Converts machine units (RTIO cycles) to seconds.

        :param mu: cycle count to convert.
        """
        return mu*self.ref_period

    @kernel
    def get_rtio_counter_mu(self):
        return rtio_get_counter()

    @kernel
    def get_drtio_link_status(self, linkno):
        """Returns whether the specified DRTIO link is up.

        This is particularly useful in startup kernels to delay
        startup until certain DRTIO links are up."""
        return drtio_get_link_status(linkno)

    @kernel
    def reset(self):
        """Clear RTIO FIFOs, release RTIO PHY reset, and set the time cursor
        at the current value of the hardware RTIO counter plus a margin of
        125000 machine units."""
        rtio_init()
        at_mu(rtio_get_counter() + 125000)

    @kernel
    def break_realtime(self):
        """Set the time cursor after the current value of the hardware RTIO
        counter plus a margin of 125000 machine units.

        If the time cursor is already after that position, this function
        does nothing."""
        min_now = rtio_get_counter() + 125000
        if now_mu() < min_now:
            at_mu(min_now)
