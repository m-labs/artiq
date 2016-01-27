import unittest

from artiq.devices.lda.driver import Ldasim
from artiq.language.units import dB
from artiq.test.hardware_testbench import ControllerCase, with_controllers


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
    @with_controllers("lda")
    def test_attenuation(self):
        self.cont = self.device_mgr.get("lda")
        GenericLdaTest.test_attenuation(self)


class TestLdaSim(GenericLdaTest, unittest.TestCase):
    def setUp(self):
        self.cont = Ldasim()
