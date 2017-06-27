import unittest
import sys

from artiq.devices.lda.driver import Ldasim
from artiq.language.units import dB
from artiq.test.hardware_testbench import GenericControllerCase, ControllerCase


class GenericLdaTest:
    def test_attenuation(self):
        step = self.cont.get_att_step_size()
        attmax = self.cont.get_att_max()
        test_vector = [i*step*dB for i in range(0, int(attmax*int(1/step)+1))]
        for i in test_vector:
            with self.subTest(i=i):
                self.cont.set_attenuation(i)
                j = self.cont.get_attenuation()
                self.assertEqual(i, j)


class TestLda(ControllerCase, GenericLdaTest):
    def setUp(self):
        ControllerCase.setUp(self)
        self.start_controller("lda")
        self.cont = self.device_mgr.get("lda")


class TestLdaSim(GenericControllerCase, GenericLdaTest):
    def get_device_db(self):
        return {
            "lda": {
                "type": "controller",
                "host": "::1",
                "port": 3253,
                "command": (sys.executable.replace("\\", "\\\\")
                            + " -m artiq.frontend.aqctl_lda "
                            + "-p {port} --simulation")
            }
        }

    def setUp(self):
        GenericControllerCase.setUp(self)
        self.start_controller("lda")
        self.cont = self.device_mgr.get("lda")
