import unittest
from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.adf5356 import (
    calculate_pll,
    split_msb_lsb_28b,
    ADF5356_MODULUS1,
    ADF5356_MAX_MODULUS2,
)


class ADF5356Exp(EnvExperiment):
    def build(self, runner):
        self.setattr_device("core")
        self.dev = self.get_device("mirny0_ch0")
        self.runner = runner

    def run(self):
        getattr(self, self.runner)()

    @kernel
    def instantiate(self):
        pass

    @kernel
    def init(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        self.dev.init()

    @kernel
    def set_get_simple(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        self.dev.init()
        self.dev.set_att_mu(0)
        f = 300.123456 * MHz
        self.dev.set_frequency(f)
        self.set_dataset("freq_set", round(f / Hz))
        self.set_dataset(
            "freq_get", round(self.dev.f_vco() / self.dev.output_divider() / Hz)
        )

    @kernel
    def set_too_high_frequency(self):
        self.dev.set_frequency(10 * GHz)

    @kernel
    def set_too_low_frequency(self):
        self.dev.set_frequency(1 * MHz)

    @kernel
    def muxout_lock_detect(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        self.dev.init()
        self.dev.set_att_mu(0)
        f = 300.123 * MHz
        self.dev.set_frequency(f)
        delay(5 * ms)
        self.set_dataset("muxout", self.dev.read_muxout())


class TestCalculateParameters(unittest.TestCase):
    def setUp(self):
        self.f_pfd = 50 * MHz
        self.mod1 = ADF5356_MODULUS1

    def test_split_msb_lsb(self):
        a = (0x123 << 14) | 0x3456
        msb, lsb = split_msb_lsb_28b(a)

        self.assertEqual(msb, 0x123)
        self.assertEqual(lsb, 0x3456)

    def test_integer_pll(self):
        p_n = 30
        n, frac1, frac2, mod2 = calculate_pll(p_n * self.f_pfd, self.f_pfd)

        self.assertEqual(p_n, n)
        self.assertEqual(frac1, 0)
        self.assertEqual(frac2, (0, 0))
        self.assertNotEqual(mod2, (0, 0))

    def test_frac1_pll(self):
        p_n = 30
        p_frac1 = 1 << 22
        n, frac1, frac2, mod2 = calculate_pll(
            (p_n + p_frac1 / self.mod1) * self.f_pfd, self.f_pfd
        )

        self.assertEqual(p_n, n)
        self.assertEqual(p_frac1, frac1)
        self.assertEqual(frac2, (0, 0))
        self.assertNotEqual(mod2, (0, 0))

    def test_frac_pll(self):
        p_n = 30
        p_frac1 = 1 << 14
        p_frac2 = 1 << 24
        p_mod2 = 1 << 25
        n, frac1, frac2, mod2 = calculate_pll(
            (p_n + (p_frac1 + p_frac2 / p_mod2) / self.mod1) * self.f_pfd, self.f_pfd
        )

        self.assertEqual(p_n, n)
        self.assertEqual(p_frac1, frac1)

        frac2 = (frac2[0] << 14) | frac2[1]
        mod2 = (mod2[0] << 14) | mod2[1]

        self.assertNotEqual(frac2, 0)
        self.assertNotEqual(mod2, 0)
        self.assertLessEqual(mod2, ADF5356_MAX_MODULUS2)

        self.assertEqual(
            self.mod1 // (p_frac1 + p_frac2 // p_mod2),
            self.mod1 // (frac1 + frac2 // mod2),
        )


class ADF5356Test(ExperimentCase):
    def test_instantiate(self):
        self.execute(ADF5356Exp, "instantiate")

    def test_init(self):
        self.execute(ADF5356Exp, "init")

    def test_set_get_simple(self):
        self.execute(ADF5356Exp, "set_get_simple")
        f_set = self.dataset_mgr.get("freq_set")
        f_get = self.dataset_mgr.get("freq_get")
        self.assertEqual(f_set, f_get)

    def test_muxout_lock_detect(self):
        self.execute(ADF5356Exp, "muxout_lock_detect")
        muxout = self.dataset_mgr.get("muxout")
        self.assertTrue(muxout)

    def test_set_too_high_frequency(self):
        with self.assertRaises(ValueError):
            self.execute(ADF5356Exp, "set_too_high_frequency")

    def test_set_too_low_frequency(self):
        with self.assertRaises(ValueError):
            self.execute(ADF5356Exp, "set_too_low_frequency")
