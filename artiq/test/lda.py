import unittest

from artiq.devices.lda.driver import Lda, Ldasim
from artiq.language.units import dB
from artiq.test.hardware_testbench import get_from_ddb


class GenericLdaTest:
    def test_attenuation(self):
        step = self.cont.get_att_step_size()
        attmax = self.cont.get_att_max()
        test_vector = [i*step*dB for i in range(0, int(attmax*int(1/step)+1))]
        for i in test_vector:
            with self.subTest(i=i):
                self.cont.set_attenuation(i)
                self.assertEqual(i, self.cont.get_attenuation())


class TestLda(GenericLdaTest, unittest.TestCase):
    def setUp(self):
        lda_serial = get_from_ddb("lda", "device")
        lda_product = get_from_ddb("lda", "product")
        self.cont = Lda(serial=lda_serial, product=lda_product)


class TestLdaSim(GenericLdaTest, unittest.TestCase):
    def setUp(self):
        self.cont = Ldasim()
