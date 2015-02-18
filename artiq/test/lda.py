import unittest
import os
from artiq.devices.lda.driver import Lda, Ldasim
from artiq.language.units import dB


no_hardware = bool(os.getenv("ARTIQ_NO_HARDWARE"))


class GenericLdaTest:
    def test_attenuation(self):
        step = self.cont.get_att_step_size().amount
        max = self.cont.get_att_max().amount
        test_vector = [i*step*dB for i in range(0, int(max*int(1/step)+1))]
        for i in test_vector:
            with self.subTest(i=i):
                self.cont.set_attenuation(i)
                self.assertEqual(i, self.cont.get_attenuation())


@unittest.skipIf(no_hardware, "no hardware")
class TestLda(GenericLdaTest, unittest.TestCase):
    def setUp(self):
        device = os.getenv("ARTIQ_LDA_DEVICE")
        serial = os.getenv("ARTIQ_LDA_SERIAL")
        args = dict()
        if device is not None:
            args["product"] = device
        if serial is not None:
            args["serial"] = serial

        self.cont = Lda(**args)


class TestLdaSim(GenericLdaTest, unittest.TestCase):
    def setUp(self):
        self.cont = Ldasim()

if __name__ == "__main__":
    unittest.main()
