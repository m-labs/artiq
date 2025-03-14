from artiq.coredevice.ad9834 import (
    AD9834_B28,
    AD9834_DIV2,
    AD9834_FSEL,
    AD9834_HLB,
    AD9834_MODE,
    AD9834_OPBITEN,
    AD9834_PIN_SW,
    AD9834_PSEL,
    AD9834_RESET,
    AD9834_SIGN_PIB,
    AD9834_SLEEP1,
    AD9834_SLEEP12,
)
from artiq.experiment import *
from artiq.language.units import MHz
from artiq.test.hardware_testbench import ExperimentCase


class AD9834Exp(EnvExperiment):
    def build(self, runner):
        self.setattr_device("core")
        self.dev = self.get_device("dds0")
        self.runner = runner

    def run(self):
        getattr(self, self.runner)()

    @kernel
    def instantiate(self):
        pass

    @kernel
    def init(self):
        self.core.reset()
        self.dev.init()
        self.set_dataset("spi_freq", self.dev.spi_freq)
        self.set_dataset("clk_freq", self.dev.clk_freq)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def frequency_to_ftw_fail(self):
        self.core.reset()
        self.dev.init()
        self.dev.frequency_to_ftw(37.6 * MHz)

    @kernel
    def turns_to_phase_fail(self):
        self.core.reset()
        self.dev.init()
        self.dev.turns_to_phase(1.1)

    @kernel
    def set_frequency_reg_fail(self):
        self.core.reset()
        self.dev.init()
        self.dev.set_frequency_reg(19, self.dev.frequency_to_ftw(10 * MHz))

    @kernel
    def set_frequency_reg(self):
        self.core.reset()
        self.dev.init()
        self.dev.set_frequency_reg(1, self.dev.frequency_to_ftw(19 * MHz))
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def set_frequency_reg_msb(self):
        self.core.reset()
        self.dev.init()
        self.dev.ctrl_reg |= AD9834_B28
        self.dev.set_frequency_reg_msb(0, 0x1111)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def set_frequency_reg_lsb(self):
        self.core.reset()
        self.dev.init()
        self.dev.ctrl_reg |= AD9834_B28 | AD9834_HLB
        self.dev.set_frequency_reg_lsb(1, 0xFFFF)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def select_frequency_reg_0(self):
        self.core.reset()
        self.dev.init()
        self.dev.select_frequency_reg(0)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg & ~(AD9834_FSEL | AD9834_PIN_SW))

    @kernel
    def select_frequency_reg_1(self):
        self.core.reset()
        self.dev.init()
        self.dev.select_frequency_reg(1)
        self.set_dataset("ctrl_reg", (self.dev.ctrl_reg | AD9834_FSEL) & ~AD9834_PIN_SW)

    @kernel
    def set_phase_reg_fail(self):
        self.core.reset()
        self.dev.init()
        self.dev.set_phase_reg(19, 0x123)

    @kernel
    def set_phase_reg(self):
        self.core.reset()
        self.dev.init()
        self.dev.set_phase_reg(0, 0x123)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def select_phase_reg_0(self):
        self.core.reset()
        self.dev.init()
        self.dev.select_phase_reg(0)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg & ~(AD9834_PSEL | AD9834_PIN_SW))

    @kernel
    def select_phase_reg_1(self):
        self.core.reset()
        self.dev.init()
        self.dev.select_phase_reg(1)
        self.set_dataset("ctrl_reg", (self.dev.ctrl_reg | AD9834_PSEL) & ~AD9834_PIN_SW)

    @kernel
    def sleep_dac_powerdown(self):
        self.core.reset()
        self.dev.init()
        self.dev.sleep(dac_pd=True)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def sleep_internal_clk_disable(self):
        self.core.reset()
        self.dev.init()
        self.dev.sleep(clk_dis=True)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def sleep(self):
        self.core.reset()
        self.dev.init()
        self.dev.sleep(dac_pd=True, clk_dis=True)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def awake(self):
        self.core.reset()
        self.dev.init()
        self.dev.awake()
        self.set_dataset(
            "ctrl_reg", self.dev.ctrl_reg & ~(AD9834_SLEEP1 | AD9834_SLEEP12)
        )

    @kernel
    def sign_bit_high_z(self):
        self.core.reset()
        self.dev.init()
        self.dev.config_sign_bit_out()
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg & ~AD9834_OPBITEN)

    @kernel
    def sign_bit_msb_2(self):
        self.core.reset()
        self.dev.init()
        self.dev.config_sign_bit_out(msb_2=True)
        self.set_dataset(
            "ctrl_reg",
            (self.dev.ctrl_reg | AD9834_OPBITEN)
            & ~(AD9834_MODE | AD9834_SIGN_PIB | AD9834_DIV2),
        )

    @kernel
    def sign_bit_msb(self):
        self.core.reset()
        self.dev.init()
        self.dev.config_sign_bit_out(msb=True)
        self.set_dataset(
            "ctrl_reg",
            (self.dev.ctrl_reg | AD9834_MODE | AD9834_SIGN_PIB)
            & ~(AD9834_MODE | AD9834_SIGN_PIB),
        )

    @kernel
    def sign_bit_comp_out(self):
        self.core.reset()
        self.dev.init()
        self.dev.config_sign_bit_out(comp_out=True)
        self.set_dataset(
            "ctrl_reg",
            (self.dev.ctrl_reg | AD9834_OPBITEN | AD9834_SIGN_PIB | AD9834_DIV2)
            & ~AD9834_MODE,
        )

    @kernel
    def enable_triangular_waveform(self):
        self.core.reset()
        self.dev.init()
        self.dev.enable_triangular_waveform()
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg | AD9834_MODE)

    @kernel
    def disable_triangular_waveform(self):
        self.core.reset()
        self.dev.init()
        self.dev.disable_triangular_waveform()
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg & ~AD9834_MODE)

    ## The following tests should be hooked up to an oscilloscope
    ## to monitor the waveforms
    @kernel
    def single_tone(self):
        self.core.reset()
        self.dev.init()
        self.dev.set_frequency_reg(0, self.dev.frequency_to_ftw(1 * MHz))
        self.dev.select_frequency_reg(0)
        self.dev.output_enable()
        delay(5 * s)
        self.dev.enable_reset()
        self.core.wait_until_mu(now_mu())

    @kernel
    def toggle_frequency(self):
        self.core.reset()
        self.dev.init()
        self.dev.set_frequency_reg(0, self.dev.frequency_to_ftw(1 * MHz))
        self.dev.set_frequency_reg(1, self.dev.frequency_to_ftw(2 * MHz))
        self.dev.select_frequency_reg(0)
        self.dev.output_enable()

        for _ in range(6):
            self.dev.select_frequency_reg(0)
            delay(1 * s)
            self.dev.select_frequency_reg(1)
            delay(1 * s)

        self.dev.enable_reset()
        self.core.wait_until_mu(now_mu())

    @kernel
    def toggle_phase(self):
        self.core.reset()
        self.dev.init()
        self.dev.set_frequency_reg(0, self.dev.frequency_to_ftw(1 * MHz))
        self.dev.select_frequency_reg(0)
        self.dev.set_phase_reg(0, 0x0)
        self.dev.set_phase_reg(1, 0x7FF)
        self.dev.output_enable()

        for _ in range(300000):
            self.dev.select_phase_reg(0)
            delay(10 * us)
            self.dev.select_phase_reg(1)
            delay(10 * us)

        self.dev.enable_reset()
        self.core.wait_until_mu(now_mu())

    @kernel
    def set_mu(self):
        self.core.reset()
        self.dev.init()
        freq_word = self.dev.frequency_to_ftw(1 * MHz)
        phase_word = self.dev.turns_to_phase(0.5)
        self.dev.set_mu(freq_word, phase_word, 0, 1)

        delay(5 * s)

        self.dev.enable_reset()
        self.core.wait_until_mu(now_mu())

    @kernel
    def set(self):
        self.core.reset()
        self.dev.init()
        self.dev.set(2 * MHz, 0.5, 1, 0)

        delay(5 * s)

        self.dev.enable_reset()
        self.core.wait_until_mu(now_mu())


class AD9834Test(ExperimentCase):
    def test_instantiate(self):
        self.execute(AD9834Exp, "instantiate")

    def test_init(self):
        self.execute(AD9834Exp, "init")
        spi_freq = self.dataset_mgr.get("spi_freq")
        clk_freq = self.dataset_mgr.get("clk_freq")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(spi_freq, 10 * MHz)
        self.assertEqual(clk_freq, 75 * MHz)
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_frequency_to_ftw_fail(self):
        with self.assertRaises(AssertionError):
            self.execute(AD9834Exp, "frequency_to_ftw_fail")

    def test_turns_to_phase_fail(self):
        with self.assertRaises(AssertionError):
            self.execute(AD9834Exp, "turns_to_phase_fail")

    def test_set_frequency_reg_fail(self):
        with self.assertRaises(AssertionError):
            self.execute(AD9834Exp, "set_frequency_reg_fail")

    def test_set_frequency_reg(self):
        self.execute(AD9834Exp, "set_frequency_reg")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_B28 | AD9834_RESET)

    def test_set_frequency_reg_msb(self):
        self.execute(AD9834Exp, "set_frequency_reg_msb")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_HLB | AD9834_RESET)

    def test_set_frequency_reg_lsb(self):
        self.execute(AD9834Exp, "set_frequency_reg_lsb")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_select_frequency_reg_0(self):
        self.execute(AD9834Exp, "select_frequency_reg_0")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_select_frequency_reg_1(self):
        self.execute(AD9834Exp, "select_frequency_reg_1")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_FSEL | AD9834_RESET)

    def test_set_phase_reg_fail(self):
        with self.assertRaises(AssertionError):
            self.execute(AD9834Exp, "set_phase_reg_fail")

    def test_set_phase_reg(self):
        self.execute(AD9834Exp, "set_phase_reg")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_select_phase_reg_0(self):
        self.execute(AD9834Exp, "select_phase_reg_0")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_select_phase_reg_1(self):
        self.execute(AD9834Exp, "select_phase_reg_1")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_PSEL | AD9834_RESET)

    def test_sleep_dac_powerdown(self):
        self.execute(AD9834Exp, "sleep_dac_powerdown")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_SLEEP12 | AD9834_RESET)

    def test_sleep_internal_clk_disable(self):
        self.execute(AD9834Exp, "sleep_internal_clk_disable")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_SLEEP1 | AD9834_RESET)

    def test_sleep(self):
        self.execute(AD9834Exp, "sleep")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(
            ctrl_reg, 0x0000 | AD9834_SLEEP1 | AD9834_SLEEP12 | AD9834_RESET
        )

    def test_awake(self):
        self.execute(AD9834Exp, "awake")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_sign_bit_high_z(self):
        self.execute(AD9834Exp, "sign_bit_high_z")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_sign_bit_msb_2(self):
        self.execute(AD9834Exp, "sign_bit_msb_2")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_OPBITEN | AD9834_RESET)

    def test_sign_bit_msb(self):
        self.execute(AD9834Exp, "sign_bit_msb")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_OPBITEN | AD9834_DIV2 | AD9834_RESET)

    def test_sign_bit_comp_out(self):
        self.execute(AD9834Exp, "sign_bit_comp_out")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(
            ctrl_reg,
            0x0000 | AD9834_OPBITEN | AD9834_SIGN_PIB | AD9834_DIV2 | AD9834_RESET,
        )

    def test_enble_triangular_waveform(self):
        self.execute(AD9834Exp, "enable_triangular_waveform")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_MODE | AD9834_RESET)

    def test_disble_triangular_waveform(self):
        self.execute(AD9834Exp, "disable_triangular_waveform")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    ## Waveform Tests
    def test_single_tone(self):
        print("Running waveform test:", self._testMethodName)
        self.execute(AD9834Exp, "single_tone")

    def test_toggle_frequency(self):
        print("Running waveform test:", self._testMethodName)
        self.execute(AD9834Exp, "toggle_frequency")

    def test_toggle_phase(self):
        print("Running waveform test:", self._testMethodName)
        self.execute(AD9834Exp, "toggle_phase")

    def test_set_mu(self):
        print("Running waveform test:", self._testMethodName)
        self.execute(AD9834Exp, "set_mu")

    def test_set(self):
        print("Running waveform test:", self._testMethodName)
        self.execute(AD9834Exp, "set")
