import unittest
import linecache
import artiq.coredevice.exceptions as exceptions

from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.language.embedding_map import EmbeddingMap
from artiq.coredevice.core import Core, test_exception_id_sync
from artiq.coredevice.dma import CoreDMA
from numpy import int32

"""
Test sync in exceptions raised between host and kernel
Check `artiq.compiler.embedding` and `artiq::firmware::ksupport::eh_artiq`

Considers the following two cases:
    1) Exception raised on kernel and passed to host
    2) Exception raised in a host function called from kernel
Ensures same exception is raised on both kernel and host in either case
"""

exception_names = EmbeddingMap().string_map


@compile
class _TestExceptionSync(EnvExperiment):
    def build(self):
        self.setattr_device("core")
    
    @rpc
    def _raise_exception_host(self, id: int32):
        exn = exception_names[id].split('.')[-1].split(':')[-1]
        exn = getattr(exceptions, exn)
        raise exn

    @kernel
    def raise_exception_host(self, id: int32):
        self._raise_exception_host(id)

    @kernel
    def raise_exception_kernel(self, id: int32):
        test_exception_id_sync(id)


class ExceptionTest(ExperimentCase):
    def test_raise_exceptions_kernel(self):
        exp = self.create(_TestExceptionSync)
        
        for id, name in exception_names.items():
            name = name.split('.')[-1].split(':')[-1]
            with self.assertRaises(getattr(exceptions, name)) as ctx:
                exp.raise_exception_kernel(id)
            self.assertEqual(str(ctx.exception).strip("'"), name)
            
            
    def test_raise_exceptions_host(self):
        exp = self.create(_TestExceptionSync)

        for id, name in exception_names.items():
            name = name.split('.')[-1].split(':')[-1]
            with self.assertRaises(getattr(exceptions, name)) as ctx:
                exp.raise_exception_host(id)


@compile
class CoreExceptionTraceback(EnvExperiment):
    core: KernelInvariant[Core]
    core_dma: KernelInvariant[CoreDMA]
    trace_name: KernelInvariant[str]

    def build(self):
        self.setattr_device("core")
        self.setattr_device("core_dma")
        self.trace_name = "dummy_trace"
    
    @kernel
    def run(self):
        self.core_dma.prepare_record(self.trace_name)
        with self.core_dma.recorder:
            pass
        self.core_dma.erase(self.trace_name)
        self.core_dma.playback(self.trace_name)


class TracebackTest(ExperimentCase):
    def test_core_exception_traceback(self):
        with self.assertRaises(exceptions.DMAError) as exn_context:
            self.execute(CoreExceptionTraceback)

        core_exn = exn_context.exception.artiq_core_exception
        traceback = core_exn.traceback[core_exn.exception_info[0][1]:]
        self.assertGreater(len(traceback), 0, "traceback is missing")

        def get_backtrace_records():
            for filename, line, *_, inlined in traceback:
                for inlined_filename, inlined_line, *_ in reversed(inlined):
                    yield inlined_filename, inlined_line
                yield filename, line

        for filename, line in get_backtrace_records():
            source_line = linecache.getline(filename, line)
            if source_line:
                self.assertEqual(
                    source_line.strip(),
                    "self.core_dma.playback(self.trace_name)",
                    "traceback found an incorrect source of exception")
                return

        self.fail("traceback failed to find the source of exception")
