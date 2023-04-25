import re

from artiq.experiment import *
from artiq.master.worker_db import DeviceError
from artiq.test.hardware_testbench import ExperimentCase


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


class TestExceptions(ExperimentCase):
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
