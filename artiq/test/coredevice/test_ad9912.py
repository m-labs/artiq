from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase

from artiq.coredevice.urukul import STA_PROTO_REV_9

# Set to desired devices
CPLD = "urukul_cpld"
DDS = "urukul_ch1"


class AD9912Exp(EnvExperiment):
    def build(self, runner):
        self.setattr_device("core")
        self.cpld = self.get_device(CPLD)
        self.dev = self.get_device(DDS)
        self.runner = runner

    def run(self):
        getattr(self, self.runner)()

    @kernel
    def instantiate(self):
        pass

    @kernel
    def init(self):
        self.core.break_realtime()
        self.cpld.init()
        self.dev.init()

    @kernel
    def set_get_att(self):
        self.core.break_realtime()
        self.cpld.init()
        self.dev.init()
        f = 81.2345 * MHz
        p = 0.33
        a = 0.89
        att = 20 * dB
        self.dev.set_att(att)
        self.dev.set(frequency=f, phase=p)
        self.core.break_realtime()
        att_mu = self.dev.get_att_mu()
        self.set_dataset("att_set", self.cpld.att_to_mu(att))
        self.set_dataset("att_get", att_mu)

    @kernel
    def set_speed(self):
        self.core.break_realtime()
        self.cpld.init()
        self.dev.init()
        f = 81.2345 * MHz
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.set(frequency=f, phase=0.33)
        self.set_dataset(
            "dt", self.core.mu_to_seconds(self.core.get_rtio_counter_mu() - t0) / n
        )

    @kernel
    def set_speed_mu(self):
        self.core.break_realtime()
        self.cpld.init()
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.set_mu(0x12345678, 0x1234)
        self.set_dataset(
            "dt", self.core.mu_to_seconds(self.core.get_rtio_counter_mu() - t0) / n
        )

    @kernel
    def sw_readback(self):
        self.core.break_realtime()
        self.cpld.init()
        self.dev.init()
        self.dev.cfg_sw(False)
        self.dev.sw.on()
        sw_on = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        delay(10 * us)
        self.dev.sw.off()
        sw_off = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        self.set_dataset("sw", (sw_on, sw_off))

    @kernel
    def cfg_sw_readback(self):
        self.core.break_realtime()
        self.cpld.init()
        self.dev.init()
        self.dev.cfg_sw(True)
        cfg_sw_on = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        delay(10 * us)
        self.dev.cfg_sw(False)
        cfg_sw_off = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        self.set_dataset("cfg_sw", (cfg_sw_on, cfg_sw_off))

    @kernel
    def single_tone(self):
        self.core.reset()
        self.cpld.init()

        # Set ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dev.cfg_att_en(True)

        self.dev.init()

        delay(10 * ms)

        self.dev.set(100 * MHz)
        self.dev.cfg_sw(True)
        self.dev.set_att(1.0)

        delay(5 * s)

        self.dev.cfg_sw(False)

        # UnSet ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dev.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def sw_single_tone(self):
        self.core.reset()
        self.cpld.init()

        # Set ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dev.cfg_att_en(True)

        self.dev.init()

        delay(10 * ms)

        self.dev.set(150 * MHz)

        self.dev.set_att(1.0)
        self.dev.sw.on()
        delay(2 * s)
        self.dev.sw.off()
        delay(2 * s)
        self.dev.sw.on()
        delay(2 * s)
        self.dev.sw.off()

        # UnSet ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dev.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())


class AD9912Test(ExperimentCase):
    def test_instantiate(self):
        self.execute(AD9912Exp, "instantiate")

    def test_init(self):
        self.execute(AD9912Exp, "init")

    def test_set_get_att(self):
        self.execute(AD9912Exp, "set_get_att")
        get = self.dataset_mgr.get("att_get")
        set_ = self.dataset_mgr.get("att_set")
        self.assertEqual(get, set_)

    def test_set_speed(self):
        self.execute(AD9912Exp, "set_speed")
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 70 * us)

    def test_set_speed_mu(self):
        self.execute(AD9912Exp, "set_speed_mu")
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 11 * us)

    def test_sw_readback(self):
        if "sw_device" in self.device_mgr.get_desc(DDS).get("arguments", []):
            self.execute(AD9912Exp, "sw_readback")
            self.assertEqual(self.dataset_mgr.get("sw"), (1, 0))

    def test_cfg_sw_readback(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(AD9912Exp, "cfg_sw_readback")
            self.assertEqual(self.dataset_mgr.get("cfg_sw"), (1, 0))

    def test_single_tone(self):
        self.execute(AD9912Exp, "single_tone")

    def test_sw_single_tone(self):
        if "sw_device" in self.device_mgr.get_desc(DDS).get("arguments", []):
            self.execute(AD9912Exp, "sw_single_tone")
