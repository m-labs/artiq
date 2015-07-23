import unittest

from artiq.devices.novatech409b.driver import Novatech409B
from artiq.test.hardware_testbench import get_from_ddb


class GenericNovatech409BTest:
    def test_parameters_readback(self):
        # write sample data and read it back
        for i in range(4):
            self.driver.set_freq(i, 1e6)
            self.driver.set_phase(i, 0.5)
            self.driver.set_gain(i, 0.25)
        result = self.driver.get_status()

        # check for expected status message; ignore all but first 23 bytes
        # compare with previous result extracted from Novatech
        for i in range(4):
            r = result[i]
            self.assertEqual(r[0:23], "00989680 2000 01F5 0000")


class TestNovatech409B(GenericNovatech409BTest, unittest.TestCase):
    def setUp(self):
        novatech409b_device = get_from_ddb("novatech409b", "device")
        self.driver = Novatech409B(novatech409b_device)


class TestNovatech409BSim(GenericNovatech409BTest, unittest.TestCase):
    def setUp(self):
        self.driver = Novatech409B(None)
