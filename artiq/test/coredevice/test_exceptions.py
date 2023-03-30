import logging
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
        for _ in range(1000):
            self.led.on()
            self.led.off()


class TestExceptions(ExperimentCase):
    def test_custom_formatted_kernel_exception(self):
        with self.assertLogs() as captured:
            with self.assertRaisesRegex(CustomException, r"CustomException\(\d+\): \{foo\}"):
                self.execute(KernelFmtException)
        self.assertEqual(captured.output, [
            "ERROR:artiq.coredevice.comm_kernel:Couldn't format exception message `{foo}`: KeyError: 'foo'"])

    def test_nested_formatted_kernel_exception(self):
        with self.assertLogs() as captured:
            with self.assertRaisesRegex(CustomException,
                                        re.compile(
                                            r"CustomException\(\d+\): \{foo\}.*?RTIOUnderflow\(\d+\): \{bar\}.*?RTIOOverflow\(\d+\): \{bizz\}.*?RTIOUnderflow\(\d+\): \{buzz\}",
                                            re.DOTALL)):
                self.execute(KernelNestedFmtException)
        self.assertEqual(captured.output, [
            "ERROR:artiq.coredevice.comm_kernel:Couldn't format exception message `{foo}`: KeyError: 'foo'"])

    def test_rtio_underflow(self):
        with self.assertLogs() as captured:
            with self.assertRaisesRegex(RTIOUnderflow,
                                        re.compile(
                                            r"RTIO underflow at channel 0x\d+?:led\d*?, \d+? mu, slack -\d+? mu.*?RTIOUnderflow\(\d+\): RTIO underflow at channel 0x\d+?:led\d+?, \d+? mu, slack -\d+? mu",
                                            re.DOTALL)):
                self.execute(KernelRTIOUnderflow)
        self.assertEqual(captured.output, ["WARNING:artiq.coredevice.comm_kernel:sequence error(s) reported during kernel execution"])
