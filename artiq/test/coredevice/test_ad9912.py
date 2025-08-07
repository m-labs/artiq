from numpy import int32, int64

from artiq.coredevice.ad9912 import AD9912
from artiq.coredevice.core import Core
from artiq.coredevice.urukul import (
    CPLD as UrukulCPLD,
    STA_PROTO_REV_8,
    STA_PROTO_REV_9,
)
from artiq.experiment import *
from artiq.test.coredevice.test_ad9910_waveform import io_update_device
from artiq.test.hardware_testbench import ExperimentCase

# Set to desired devices
CPLD = "urukul_cpld"
DDS = "urukul_ch1"


@compile
class AD9912Exp(EnvExperiment):
    core: KernelInvariant[Core]
    cpld: KernelInvariant[UrukulCPLD]
    dev: KernelInvariant[AD9912]
    io_update_device: Kernel[bool]

    def build(self, runner, io_update_device=True):
        self.setattr_device("core")
        self.cpld = self.get_device(CPLD)
        self.dev = self.get_device(DDS)
        self.runner = runner
        self.io_update_device = io_update_device

    def run(self):
        getattr(self, self.runner)()

    @rpc
    def report_int32(self, name: str, data: int32):
        self.set_dataset(name, data)

    @rpc
    def report_list_int32(self, name: str, data: list[int32]):
        self.set_dataset(name, data)

    @rpc
    def report_float(self, name: str, data: float):
        self.set_dataset(name, data)

    @kernel
    def instantiate(self):
        pass

    @kernel
    def init(self):
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def set_get_att(self):
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        f = 81.2345 * MHz
        p = 0.33
        a = 0.89
        att = 20. * dB
        self.dev.set_att(att)
        self.dev.set(frequency=f, phase=p)
        self.core.break_realtime()
        att_mu = self.dev.get_att_mu()
        self.report_int32("att_set", self.cpld.att_to_mu(att))
        self.report_int32("att_get", att_mu)
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def set_speed(self):
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        f = 81.2345 * MHz
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.set(frequency=f, phase=0.33)
        self.report_float(
            "dt", self.core.mu_to_seconds(self.core.get_rtio_counter_mu() - t0) / float(n)
        )
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def set_speed_mu(self):
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.set_mu(int64(0x12345678), 0x1234)
        self.report_float(
            "dt", self.core.mu_to_seconds(self.core.get_rtio_counter_mu() - t0) / float(n)
        )
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def sw_readback(self):
        if self.dev.sw.is_some():
            self.core.break_realtime()
            self.cpld.init()
            if not self.io_update_device:
                # Set MASK_NU to trigger CFG.IO_UPDATE
                self.dev.cfg_mask_nu(True)
            self.dev.init()
            self.dev.cfg_sw(False)
            self.dev.sw.unwrap().on()
            sw_on = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
            self.core.delay(10. * us)
            self.dev.sw.unwrap().off()
            sw_off = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
            self.report_list_int32("sw", [sw_on, sw_off])
            if not self.io_update_device:
                self.core.break_realtime()
                # Unset MASK_NU to un-trigger CFG.IO_UPDATE
                self.dev.cfg_mask_nu(False)

    @kernel
    def cfg_sw_readback(self):
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        self.dev.cfg_sw(True)
        cfg_sw_on = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        self.core.delay(10. * us)
        self.dev.cfg_sw(False)
        cfg_sw_off = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        self.report_list_int32("cfg_sw", [cfg_sw_on, cfg_sw_off])
        if not self.io_update_device:
            self.core.break_realtime()
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def single_tone(self):
        self.core.reset()
        self.cpld.init()

        # Set ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dev.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()

        self.core.delay(10. * ms)

        self.dev.set(100. * MHz)
        self.dev.cfg_sw(True)
        self.dev.set_att(1.0)

        self.core.delay(5. * s)

        self.dev.cfg_sw(False)

        # Unset ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dev.cfg_att_en(False)
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def sw_single_tone(self):
        self.core.reset()
        self.cpld.init()

        # Set ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dev.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)

        self.dev.init()

        self.core.delay(10. * ms)

        self.dev.set(150. * MHz)

        self.dev.set_att(1.0)
        self.dev.sw.unwrap().on()
        self.core.delay(2. * s)
        self.dev.sw.unwrap().off()
        self.core.delay(2. * s)
        self.dev.sw.unwrap().on()
        self.core.delay(2. * s)
        self.dev.sw.unwrap().off()

        # Unset ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dev.cfg_att_en(False)
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

        self.core.wait_until_mu(now_mu())


class AD9912Test(ExperimentCase):
    def test_instantiate(self):
        self.execute(AD9912Exp, "instantiate")

    @io_update_device(CPLD, True, False)
    def test_init(self, io_update_device):
        self.execute(AD9912Exp, "init", io_update_device=io_update_device)

    @io_update_device(CPLD, True, False)
    def test_set_get_att(self, io_update_device):
        self.execute(AD9912Exp, "set_get_att", io_update_device=io_update_device)
        get = self.dataset_mgr.get("att_get")
        set_ = self.dataset_mgr.get("att_set")
        self.assertEqual(get, set_)

    @io_update_device(CPLD, True)
    def test_set_speed(self, io_update_device):
        self.execute(AD9912Exp, "set_speed", io_update_device=io_update_device)
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 70 * us)

    @io_update_device(CPLD, True)
    def test_set_speed_mu(self, io_update_device):
        self.execute(AD9912Exp, "set_speed_mu", io_update_device=io_update_device)
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 11 * us)

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_8)
    def test_sw_readback(self, io_update_device):
        if "sw_device" in self.device_mgr.get_desc(DDS).get("arguments", []):
            self.execute(AD9912Exp, "sw_readback", io_update_device=io_update_device)
            self.assertEqual(self.dataset_mgr.get("sw"), [1, 0])

    @io_update_device(CPLD, True, False)
    def test_cfg_sw_readback(self, io_update_device):
        self.execute(AD9912Exp, "cfg_sw_readback", io_update_device=io_update_device)
        self.assertEqual(self.dataset_mgr.get("cfg_sw"), [1, 0])

    @io_update_device(CPLD, True, False)
    def test_single_tone(self, io_update_device):
        self.execute(AD9912Exp, "single_tone", io_update_device=io_update_device)

    @io_update_device(CPLD, True, False)
    def test_sw_single_tone(self, io_update_device):
        if "sw_device" in self.device_mgr.get_desc(DDS).get("arguments", []):
            self.execute(AD9912Exp, "sw_single_tone", io_update_device=io_update_device)
