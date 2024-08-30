import os, sys, tempfile, subprocess, io
from functools import wraps
from numpy import int32, int64

import nac3artiq

from artiq.language.core import *
from artiq.language.core import _ConstGenericMarker
from artiq.language import core as core_language
from artiq.language.units import *
from artiq.language.embedding_map import EmbeddingMap

from artiq.coredevice.comm_kernel import CommKernel, CommKernelDummy


@extern
def rtio_init():
    raise NotImplementedError("syscall not simulated")

@extern
def rtio_get_destination_status(destination: int32) -> bool:
    raise NotImplementedError("syscall not simulated")

@extern
def rtio_get_counter() -> int64:
    raise NotImplementedError("syscall not simulated")

@extern
def test_exception_id_sync(id: int32):
    raise NotImplementedError("syscall not simulated")

artiq_builtins = {
    "none": none,
    "virtual": virtual,
    "_ConstGenericMarker": _ConstGenericMarker,
    "Option": Option,
}


@nac3
class Core:
    """Core device driver.

    :param host: hostname or IP address of the core device.
    :param ref_period: period of the reference clock for the RTIO subsystem.
        On platforms that use clock multiplication and SERDES-based PHYs,
        this is the period after multiplication. For example, with a RTIO core
        clocked at 125MHz and a SERDES multiplication factor of 8, the
        reference period is ``1 ns``.
        The machine time unit (``mu``) is equal to this period.
    :param ref_multiplier: ratio between the RTIO fine timestamp frequency
        and the RTIO coarse timestamp frequency (e.g. SERDES multiplication
        factor).
    :param analyzer_proxy: name of the core device analyzer proxy to trigger
        (optional).
    :param analyze_at_run_end: automatically trigger the core device analyzer
        proxy after the Experiment's run stage finishes.
    """
    ref_period: KernelInvariant[float]
    ref_multiplier: KernelInvariant[int32]
    coarse_ref_period: KernelInvariant[float]

    def __init__(self, dmgr,
                 host, ref_period,
                 analyzer_proxy=None, analyze_at_run_end=False,
                 ref_multiplier=8,
                 target="rv32g", satellite_cpu_targets={}):
        self.ref_period = ref_period
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

        self.target = target
        self.analyzed = False
        self.compiler = nac3artiq.NAC3(target, artiq_builtins)
        
        self.analyzer_proxy_name = analyzer_proxy
        self.analyze_at_run_end = analyze_at_run_end
        self.analyzer_proxy = None

    def notify_run_end(self):
        if self.analyze_at_run_end:
            self.trigger_analyzer_proxy()

    def close(self):
        """Disconnect core device and close sockets. 
        """
        self.comm.close()

    def compile(self, method, args, kwargs, embedding_map, file_output=None, target=None):
        if target is not None:
            # NAC3TODO: subkernels
            raise NotImplementedError

        if not self.analyzed:
            self.compiler.analyze(core_language._registered_functions, core_language._registered_classes)
            self.analyzed = True

        if hasattr(method, "__self__"):
            obj = method.__self__
            name = method.__name__
        else:
            obj = method
            name = ""

        if file_output is None:
            return self.compiler.compile_method_to_mem(obj, name, args, embedding_map)
        else:
            self.compiler.compile_method_to_file(obj, name, args, file_output, embedding_map)

    def run(self, function, args, kwargs):
        embedding_map = EmbeddingMap()
        kernel_library = self.compile(function, args, kwargs, embedding_map)

        self._run_compiled(kernel_library, embedding_map)

    def _run_compiled(self, kernel_library, embedding_map):
        if self.first_run:
            self.comm.check_system_info()
            self.first_run = False

        symbolizer = lambda addresses: symbolize(kernel_library, addresses)

        self.comm.load(kernel_library)
        self.comm.run()
        self.comm.serve(embedding_map, symbolizer)

    def precompile(self, function, *args, **kwargs):
        """Precompile a kernel and return a callable that executes it on the core device
        at a later time.

        Arguments to the kernel are set at compilation time and passed to this function,
        as additional positional and keyword arguments.
        The returned callable accepts no arguments.

        Precompiled kernels may use RPCs and subkernels.

        Object attributes at the beginning of a precompiled kernel execution have the
        values they had at precompilation time. If up-to-date values are required,
        use RPC to read them.
        Similarly, modified values are not written back, and explicit RPC should be used
        to modify host objects.
        Carefully review the source code of drivers calls used in precompiled kernels, as
        they may rely on host object attributes being transfered between kernel calls.
        Examples include code used to control DDS phase, and Urukul RF switch control
        via the CPLD register.

        The return value of the callable is the return value of the kernel, if any.

        The callable may be called several times.
        """
        if not getattr(function, "__artiq_kernel__"):
            raise ValueError("Argument is not a kernel")

        embedding_map = EmbeddingMap()
        kernel_library = self.compile(function, args, kwargs, embedding_map)

        @wraps(function)
        def run_precompiled():
            # NAC3TODO: support returning values
            # https://git.m-labs.hk/M-Labs/nac3/issues/101
            self._run_compiled(kernel_library, embedding_map)

        return run_precompiled

    @portable
    def seconds_to_mu(self, seconds: float) -> int64:
        """Convert seconds to the corresponding number of machine units
        (fine RTIO cycles).

        :param seconds: time (in seconds) to convert.
        """
        return round64(seconds/self.ref_period)

    @portable
    def mu_to_seconds(self, mu: int64) -> float:
        """Convert machine units (fine RTIO cycles) to seconds.

        :param mu: cycle count to convert.
        """
        return float(mu)*self.ref_period

    @kernel
    def delay(self, dt: float):
        delay_mu(self.seconds_to_mu(dt))

    @kernel
    def get_rtio_counter_mu(self) -> int64:
        """Retrieve the current value of the hardware RTIO timeline counter.

        As the timing of kernel code executed on the CPU is inherently
        non-deterministic, the return value is by necessity only a lower bound
        for the actual value of the hardware register at the instant when
        execution resumes in the caller.

        For a more detailed description of these concepts, see :doc:`rtio`.
        """
        return rtio_get_counter()

    @kernel
    def wait_until_mu(self, cursor_mu: int64):
        """Block execution until the hardware RTIO counter reaches the given
        value (see :meth:`get_rtio_counter_mu`).

        If the hardware counter has already passed the given time, the function
        returns immediately.
        """
        while self.get_rtio_counter_mu() < cursor_mu:
            pass

    @kernel
    def get_rtio_destination_status(self, destination: int32) -> bool:
        """Returns whether the specified RTIO destination is up.
        This is particularly useful in startup kernels to delay
        startup until certain DRTIO destinations are available."""
        return rtio_get_destination_status(destination)

    @kernel
    def reset(self):
        """Clear RTIO FIFOs, release RTIO PHY reset, and set the time cursor
        at the current value of the hardware RTIO counter plus a margin of
        125000 machine units."""
        rtio_init()
        at_mu(rtio_get_counter() + int64(125000))

    @kernel
    def break_realtime(self):
        """Set the time cursor after the current value of the hardware RTIO
        counter plus a margin of 125000 machine units.

        If the time cursor is already after that position, this function
        does nothing."""
        min_now = rtio_get_counter() + int64(125000)
        if now_mu() < min_now:
            at_mu(min_now)
    
    def trigger_analyzer_proxy(self):
        """Causes the core analyzer proxy to retrieve a dump from the device,
        and distribute it to all connected clients (typically dashboards).

        Returns only after the dump has been retrieved from the device.

        Raises :exc:`IOError` if no analyzer proxy has been configured, or if the
        analyzer proxy fails. In the latter case, more details would be
        available in the proxy log.
        """
        if self.analyzer_proxy is None:
            if self.analyzer_proxy_name is not None:
                self.analyzer_proxy = self.dmgr.get(self.analyzer_proxy_name)
        if self.analyzer_proxy is None:
            raise IOError("No analyzer proxy configured")
        else:
            self.analyzer_proxy.trigger()


class RunTool:
    def __init__(self, pattern, **tempdata):
        self._pattern   = pattern
        self._tempdata  = tempdata
        self._tempnames = {}
        self._tempfiles = {}

    def __enter__(self):
        for key, data in self._tempdata.items():
            if data is None:
                fd, filename = tempfile.mkstemp()
                os.close(fd)
                self._tempnames[key] = filename
            else:
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    f.write(data)
                    self._tempnames[key] = f.name

        cmdline = []
        for argument in self._pattern:
            cmdline.append(argument.format(**self._tempnames))

        # https://bugs.python.org/issue17023
        windows = os.name == "nt"
        process = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True, shell=windows)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise Exception("{} invocation failed: {}".
                            format(cmdline[0], stderr))

        self._tempfiles["__stdout__"] = io.StringIO(stdout)
        for key in self._tempdata:
            if self._tempdata[key] is None:
                self._tempfiles[key] = open(self._tempnames[key], "rb")
        return self._tempfiles

    def __exit__(self, exc_typ, exc_value, exc_trace):
        for file in self._tempfiles.values():
            file.close()
        for filename in self._tempnames.values():
            os.unlink(filename)


def symbolize(library, addresses):
    if addresses == []:
        return []

    # We got a list of return addresses, i.e. addresses of instructions
    # just after the call. Offset them back to get an address somewhere
    # inside the call instruction (or its delay slot), since that's what
    # the backtrace entry should point at.
    last_inlined = None
    offset_addresses = [hex(addr - 1) for addr in addresses]
    with RunTool(["llvm-addr2line", "--addresses",  "--functions", "--inlines",
                  "--demangle", "--exe={library}"] + offset_addresses,
                 library=library) \
            as results:
        lines = iter(results["__stdout__"].read().rstrip().split("\n"))
        backtrace = []
        while True:
            try:
                address_or_function = next(lines)
            except StopIteration:
                break
            if address_or_function[:2] == "0x":
                address  = int(address_or_function[2:], 16) + 1 # remove offset
                function = next(lines)
                inlined = False
            else:
                address  = backtrace[-1][4] # inlined
                function = address_or_function
                inlined = True
            location = next(lines)

            filename, line = location.rsplit(":", 1)
            if filename == "??" or filename == "<synthesized>":
                continue
            if line == "?":
                line = -1
            else:
                line = int(line)
            # can't get column out of addr2line D:
            if inlined:
                last_inlined.append((filename, line, -1, function, address))
            else:
                last_inlined = []
                backtrace.append((filename, line, -1, function, address,
                                  last_inlined))
        return backtrace

