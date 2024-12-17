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
    FREQ_REGS,
    PHASE_REGS,
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
        self.core.break_realtime()
        self.dev.init()
        self.set_dataset("spi_freq", self.dev.spi_freq)
        self.set_dataset("clk_freq", self.dev.clk_freq)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def set_frequency_reg_fail1(self):
        self.core.break_realtime()
        frequency = 10 * MHz
        self.dev.set_frequency_reg(19, frequency)

    @kernel
    def set_frequency_reg_fail2(self):
        self.core.break_realtime()
        self.dev.set_frequency_reg(FREQ_REGS[0], 37.6 * MHz)

    @kernel
    def set_frequency_reg(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.set_frequency_reg(FREQ_REGS[1], 19 * MHz)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def set_frequency_reg_msb(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.ctrl_reg |= AD9834_B28
        self.dev.set_frequency_reg_msb(FREQ_REGS[0], 0x1111)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def set_frequency_reg_lsb(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.ctrl_reg |= AD9834_B28 | AD9834_HLB
        self.dev.set_frequency_reg_lsb(FREQ_REGS[1], 0xFFFF)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def select_frequency_reg_0(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_FSEL | AD9834_PIN_SW
        self.dev.select_frequency_reg(FREQ_REGS[0])
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def select_frequency_reg_1(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_PIN_SW
        self.dev.select_frequency_reg(FREQ_REGS[1])
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def set_phase_reg_fail(self):
        self.core.break_realtime()
        self.dev.set_phase_reg(19, 0x123)

    @kernel
    def set_phase_reg(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.set_phase_reg(PHASE_REGS[0], 0x123)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def select_phase_reg_0(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_PSEL | AD9834_PIN_SW
        self.dev.select_phase_reg(PHASE_REGS[0])
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def select_phase_reg_1(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_PIN_SW
        self.dev.select_phase_reg(PHASE_REGS[1])
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def enable_reset(self):
        self.core.break_realtime()
        self.dev.enable_reset()
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def output_enable(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_RESET
        self.dev.output_enable()
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def sleep_dac_powerdown(self):
        self.core.break_realtime()
        self.dev.sleep(dac_pd=True)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def sleep_internal_clk_disable(self):
        self.core.break_realtime()
        self.dev.sleep(clk_dis=True)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def sleep(self):
        self.core.break_realtime()
        self.dev.sleep(dac_pd=True, clk_dis=True)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def awake(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_SLEEP1 | AD9834_SLEEP12
        self.dev.sleep()
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def sign_bit_high_z(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_OPBITEN
        self.dev.config_sign_bit_out()
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def sign_bit_msb_2(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_MODE | AD9834_SIGN_PIB | AD9834_DIV2
        self.dev.config_sign_bit_out(msb_2=True)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def sign_bit_msb(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_MODE | AD9834_SIGN_PIB
        self.dev.config_sign_bit_out(msb=True)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def sign_bit_comp_out(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_MODE
        self.dev.config_sign_bit_out(comp_out=True)
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def enable_triangular_waveform(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_OPBITEN
        self.dev.enable_triangular_waveform()
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)

    @kernel
    def disable_triangular_waveform(self):
        self.core.break_realtime()
        self.dev.ctrl_reg |= AD9834_MODE
        self.dev.disable_triangular_waveform()
        self.set_dataset("ctrl_reg", self.dev.ctrl_reg)


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

    def test_set_frequency_reg_fail(self):
        with self.assertRaises(ValueError):
            self.execute(AD9834Exp, "set_frequency_reg_fail1")
        with self.assertRaises(AssertionError):
            self.execute(AD9834Exp, "set_frequency_reg_fail2")

    def test_set_frequency_reg(self):
        self.execute(AD9834Exp, "set_frequency_reg")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET | AD9834_B28)

    def test_set_frequency_reg_msb(self):
        self.execute(AD9834Exp, "set_frequency_reg_msb")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET | AD9834_HLB)

    def test_set_frequency_reg_lsb(self):
        self.execute(AD9834Exp, "set_frequency_reg_lsb")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_select_frequency_reg_0(self):
        self.execute(AD9834Exp, "select_frequency_reg_0")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000)

    def test_select_frequency_reg_1(self):
        self.execute(AD9834Exp, "select_frequency_reg_1")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_FSEL)

    def test_set_phase_reg_fail(self):
        with self.assertRaises(ValueError):
            self.execute(AD9834Exp, "set_phase_reg_fail")

    def test_set_phase_reg(self):
        self.execute(AD9834Exp, "set_phase_reg")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_select_phase_reg_0(self):
        self.execute(AD9834Exp, "select_phase_reg_0")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000)

    def test_select_phase_reg_1(self):
        self.execute(AD9834Exp, "select_phase_reg_1")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_PSEL)

    def test_enable_reset(self):
        self.execute(AD9834Exp, "enable_reset")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_RESET)

    def test_output_enable(self):
        self.execute(AD9834Exp, "output_enable")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000)

    def test_sleep_dac_powerdown(self):
        self.execute(AD9834Exp, "sleep_dac_powerdown")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_SLEEP12)

    def test_sleep_internal_clk_disable(self):
        self.execute(AD9834Exp, "sleep_internal_clk_disable")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_SLEEP1)

    def test_sleep(self):
        self.execute(AD9834Exp, "sleep")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_SLEEP1 | AD9834_SLEEP12)

    def test_awake(self):
        self.execute(AD9834Exp, "awake")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000)

    def test_sign_bit_high_z(self):
        self.execute(AD9834Exp, "sign_bit_high_z")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000)

    def test_sign_bit_msb_2(self):
        self.execute(AD9834Exp, "sign_bit_msb_2")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_OPBITEN)

    def test_sign_bit_msb(self):
        self.execute(AD9834Exp, "sign_bit_msb")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_OPBITEN | AD9834_DIV2)

    def test_sign_bit_comp_out(self):
        self.execute(AD9834Exp, "sign_bit_comp_out")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(
            ctrl_reg, 0x0000 | AD9834_OPBITEN | AD9834_SIGN_PIB | AD9834_DIV2
        )

    def test_enble_triangular_waveform(self):
        self.execute(AD9834Exp, "enable_triangular_waveform")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000 | AD9834_MODE)

    def test_disble_triangular_waveform(self):
        self.execute(AD9834Exp, "disable_triangular_waveform")
        ctrl_reg = self.dataset_mgr.get("ctrl_reg")
        self.assertEqual(ctrl_reg, 0x0000)
