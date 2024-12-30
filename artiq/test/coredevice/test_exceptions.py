import re

from artiq.experiment import *
from artiq.master.worker_db import DeviceError
from artiq.test.hardware_testbench import ExperimentCase
from artiq.compiler.embedding import EmbeddingMap
from artiq.coredevice.core import test_exception_id_sync
import artiq.coredevice.exceptions as exceptions


class CustomException(Exception):
    pass


class KernelFmtException(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        self.throw()

    def throw(self):
        raise CustomException("{foo}")


class KernelNestedFmtException(EnvExperiment):
    def build(self):
        self.setattr_device("core")

    @kernel
    def run(self):
        try:
            self.throw_foo()
        except:
            try:
                raise RTIOUnderflow("{bar}")
            except:
                try:
                    raise RTIOOverflow("{bizz}")
                except:
                    self.throw_buzz()

    def throw_foo(self):
        raise CustomException("{foo}")

    def throw_buzz(self):
        raise RTIOUnderflow("{buzz}")


class KernelRTIOUnderflow(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        try:
            self.setattr_device("led")
        except DeviceError:
            self.led = self.get_device("led0")

    @kernel
    def run(self):
        self.core.reset()
        at_mu(self.core.get_rtio_counter_mu() - 1000); self.led.on()


class ExceptionFormatTest(ExperimentCase):
    def test_custom_formatted_kernel_exception(self):
        with self.assertLogs() as captured:
            with self.assertRaisesRegex(CustomException, r"CustomException\(\d+\): \{foo\}"):
                self.execute(KernelFmtException)
        captured_lines = captured.output[0].split('\n')
        self.assertEqual([captured_lines[0], captured_lines[-1]],
                         ["ERROR:artiq.coredevice.comm_kernel:Couldn't format exception message", "KeyError: 'foo'"])

    def test_nested_formatted_kernel_exception(self):
        with self.assertLogs() as captured:
            with self.assertRaisesRegex(CustomException,
                                        re.compile(
                                            r"CustomException\(\d+\): \{foo\}.*?RTIOUnderflow\(\d+\): \{bar\}.*?RTIOOverflow\(\d+\): \{bizz\}.*?RTIOUnderflow\(\d+\): \{buzz\}",
                                            re.DOTALL)):
                self.execute(KernelNestedFmtException)
        captured_lines = captured.output[0].split('\n')
        self.assertEqual([captured_lines[0], captured_lines[-1]],
                         ["ERROR:artiq.coredevice.comm_kernel:Couldn't format exception message", "KeyError: 'foo'"])

    def test_rtio_underflow(self):
        with self.assertRaisesRegex(RTIOUnderflow,
                                    re.compile(
                                        r"RTIO underflow at channel 0x[0-9a-fA-F]*?:led\d*?, \d+? mu, slack -\d+? mu.*?RTIOUnderflow\(\d+\): RTIO underflow at channel 0x([0-9a-fA-F]+?):led\d*?, \d+? mu, slack -\d+? mu",
                                        re.DOTALL)):
            self.execute(KernelRTIOUnderflow)


"""
Test sync in exceptions raised between host and kernel
Check `artiq.compiler.embedding` and `artiq::firmware::ksupport::eh_artiq`

Considers the following two cases:
    1) Exception raised on kernel and passed to host
    2) Exception raised in a host function called from kernel
Ensures same exception is raised on both kernel and host in either case
"""

exception_names = EmbeddingMap().str_reverse_map


class _TestExceptionSync(EnvExperiment):
    def build(self):
        self.setattr_device("core")
    
    @rpc
    def _raise_exception_host(self, id):
        exn = exception_names[id].split('.')[-1].split(':')[-1]
        exn = getattr(exceptions, exn)
        raise exn

    @kernel
    def raise_exception_host(self, id):
        self._raise_exception_host(id)

    @kernel
    def raise_exception_kernel(self, id):
        test_exception_id_sync(id)

    
class ExceptionSyncTest(ExperimentCase):
    def test_raise_exceptions_kernel(self):
        exp = self.create(_TestExceptionSync)
        
        for id, name in list(exception_names.items())[::-1]:
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
