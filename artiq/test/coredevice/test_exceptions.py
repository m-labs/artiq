import re

from artiq.experiment import *
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
            self.throw()
        except:
            try:
                raise RTIOUnderflow("{bar}")
            except:
                raise RTIOOverflow("{buzz}")

    def throw(self):
        raise CustomException("{foo}")


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
                                        re.compile(r"CustomException\(\d+\): \{foo\}.*?RTIOUnderflow\(\d+\): \{bar\}.*?RTIOOverflow\(\d+\): \{buzz\}",
                                                   re.DOTALL)):
                self.execute(KernelNestedFmtException)
        self.assertEqual(captured.output, [
            "ERROR:artiq.coredevice.comm_kernel:Couldn't format exception message `{foo}`: KeyError: 'foo'"])
