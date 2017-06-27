import sys
import unittest

from artiq.test.hardware_testbench import GenericControllerCase, ControllerCase


class GenericKoradKA3005PTest:
    def test_parameters_readback(self):

        # check device ID baked into firmware
        ids = self.driver.get_id()
        self.assertEqual(ids, "KORADKA3005PV2.0")


class TestKoradKA3005P(GenericKoradKA3005PTest, ControllerCase):
    def setUp(self):
        ControllerCase.setUp(self)
        self.start_controller("koradka3005p")
        self.driver = self.device_mgr.get("koradka3005p")


class TestKoradKA3005P(GenericKoradKA3005PTest, GenericControllerCase):
    def get_device_db(self):
        return {
            "korad_ka3005p": {
                "type": "controller",
                "host": "::1",
                "port": 3256,
                "command": (sys.executable.replace("\\", "\\\\")
                            + " -m artiq.frontend.aqctl_korad_ka3005p "
                            + "-p {port} --simulation")
            }
        }

    def setUp(self):
        GenericControllerCase.setUp(self)
        self.start_controller("korad_ka3005p")
        self.driver = self.device_mgr.get("korad_ka3005p")
