import unittest
import os

from artiq.devices.lda.driver import Lda, Ldasim
from artiq.language.units import dB


lda_serial = os.getenv("ARTIQ_LDA_SERIAL")


class GenericLdaTest:
    def test_attenuation(self):
        step = self.cont.get_att_step_size()
        attmax = self.cont.get_att_max()
        test_vector = [i*step*dB for i in range(0, int(attmax*int(1/step)+1))]
        for i in test_vector:
            with self.subTest(i=i):
                self.cont.set_attenuation(i)
                self.assertEqual(i, self.cont.get_attenuation())


@unittest.skipUnless(lda_serial, "no hardware")
class TestLda(GenericLdaTest, unittest.TestCase):
    def setUp(self):
        product = os.getenv("ARTIQ_LDA_PRODUCT")
        self.cont = Lda(serial=lda_serial, product=product)


class TestLdaSim(GenericLdaTest, unittest.TestCase):
    def setUp(self):
        self.cont = Ldasim()

if __name__ == "__main__":
    unittest.main()
