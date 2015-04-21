import unittest
import os
import numpy as np

from artiq.devices.pxi6733.driver import DAQmxSim, DAQmx


pxi6733_device = os.getenv("PXI6733_DEVICE")
pxi6733_analog_output = os.getenv("PXI6733_ANALOG_OUTPUT")
pxi6733_clock = os.getenv("PXI6733_CLOCK")


class GenericPXI6733Test:
    def test_load_sample_values(self):
        test_vector = np.array([1.0, 2.0, 3.0, 4.0], dtype=float)
        self.cont.load_sample_values(test_vector)
        self.assertTrue(True)

    def test_close_1(self):
        self.cont.close()
        self.assertTrue(True)

    def test_close_2(self):
        test_vector = np.array([1.0, 2.0, 3.0, 4.0], dtype=float)
        self.cont.load_sample_values(test_vector)
        self.cont.close()
        self.assertTrue(True)


@unittest.skipUnless(pxi6733_device, "no hardware")
class TestPXI6733(GenericPXI6733Test, unittest.TestCase):
    def setUp(self):
        args = dict()
        args["device"] = bytes(pxi6733_device, "ascii")
        args["analog_output"] = bytes(pxi6733_analog_output, "ascii") \
            if pxi6733_analog_output else b"ao0"
        args["clock"] = bytes(pxi6733_clock, "ascii") \
            if pxi6733_clock else b"PFI5"
        self.cont = DAQmx(**args)


class TestPXI6733Sim(GenericPXI6733Test, unittest.TestCase):
    def setUp(self):
        self.cont = DAQmxSim()
