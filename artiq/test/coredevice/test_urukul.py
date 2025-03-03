from artiq.coredevice.urukul import STA_PROTO_REV_9, urukul_sta_rf_sw
from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase

# Set to desired device
CPLD = "urukul_cpld"


class UrukulExp(EnvExperiment):
    def build(self, runner):
        self.setattr_device("core")
        self.dev = self.get_device(CPLD)
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

    @kernel
    def cfg_write(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.cfg_write(self.dev.cfg_reg)

    @kernel
    def sta_read(self):
        self.core.break_realtime()
        self.dev.init()
        sta = self.dev.sta_read()
        self.set_dataset("sta", sta)

    @kernel
    def io_rst(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.io_rst()

    @kernel
    def switches(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.cfg_sw(0, False)
        self.dev.cfg_sw(1, True)
        self.dev.cfg_sw(3, True)
        self.dev.cfg_switches(0b1010)

    @kernel
    def switch_speed(self):
        self.core.break_realtime()
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.cfg_sw(2, bool(i & 1))
        self.set_dataset("dt", self.core.mu_to_seconds(
            self.core.get_rtio_counter_mu() - t0) / n)

    @kernel
    def switches_readback(self):
        self.core.reset()  # clear switch TTLs
        self.dev.init()
        sw_set = 0b1010
        self.dev.cfg_switches(sw_set)
        sta_get = self.dev.sta_read()
        self.set_dataset("sw_set", sw_set)
        self.set_dataset("sta_get", sta_get)

    @kernel
    def att_enables(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.cfg_att_en(0, False)
        self.dev.cfg_att_en(2, True)
        self.dev.cfg_att_en(3, True)
        self.dev.cfg_att_en_all(0b1010)

    @kernel
    def att_enable_speed(self):
        self.core.break_realtime()
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.cfg_att_en(1, bool(i & 1))
        self.set_dataset("dt", self.core.mu_to_seconds(
            self.core.get_rtio_counter_mu() - t0) / n)

    @kernel
    def att(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.att_reg = 0
        att_set = 0x12345678
        self.dev.set_all_att_mu(att_set)
        # confirm that we can set all attenuators and read back
        att_get = self.dev.get_att_mu()
        # confirm backing state
        att_reg = self.dev.att_reg
        self.set_dataset("att_set", att_set)
        self.set_dataset("att_get", att_get)
        self.set_dataset("att_reg", att_reg)

    @kernel
    def att_channel(self):
        self.core.break_realtime()
        self.dev.init()
        # clear backing state
        self.dev.att_reg = 0
        att_set = int32(0x87654321)
        # set individual attenuators
        self.dev.set_att_mu(0, 0x21)
        self.dev.set_att_mu(1, 0x43)
        self.dev.set_att_mu(2, 0x65)
        self.dev.set_att_mu(3, 0x87)
        # confirm that we can set all attenuators and read back
        att_get = self.dev.get_att_mu()
        # confirm backing state
        att_reg = self.dev.att_reg
        self.set_dataset("att_set", att_set)
        self.set_dataset("att_get", att_get)
        self.set_dataset("att_reg", att_reg)

    @kernel
    def att_channel_get(self):
        self.core.break_realtime()
        self.dev.init()
        # clear backing state
        self.dev.att_reg = 0
        att_set = [int32(0x21), int32(0x43), 
                   int32(0x65), int32(0x87)]
        # set individual attenuators
        for i in range(len(att_set)):
            self.dev.set_att_mu(i, att_set[i])
        # confirm that we can set all attenuators and read back
        att_get = [0 for _ in range(len(att_set))]
        for i in range(len(att_set)):
            self.core.break_realtime()
            att_get[i] = self.dev.get_channel_att_mu(i)
        # confirm backing state
        att_reg = self.dev.att_reg
        self.set_dataset("att_set", att_set)
        self.set_dataset("att_get", att_get)
        self.set_dataset("att_reg", att_reg)

    @kernel
    def att_speed(self):
        self.core.break_realtime()
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.set_att(3, 30 * dB)
        self.set_dataset("dt", self.core.mu_to_seconds(
            self.core.get_rtio_counter_mu() - t0) / n)

    @kernel
    def osk(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.cfg_osk(0, False)
        self.dev.cfg_osk(2, True)
        self.dev.cfg_osk(3, True)
        self.dev.cfg_osk_all(0b1010)

    @kernel
    def osk_speed(self):
        self.core.break_realtime()
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.cfg_osk(1, bool(i & 1))
        self.set_dataset("dt", self.core.mu_to_seconds(
            self.core.get_rtio_counter_mu() - t0) / n)

    @kernel
    def drctl(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.cfg_drctl(0, False)
        self.dev.cfg_drctl(1, True)
        self.dev.cfg_drctl(3, True)
        self.dev.cfg_drctl_all(0b1010)

    @kernel
    def drctl_speed(self):
        self.core.break_realtime()
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.cfg_drctl(2, bool(i & 1))
        self.set_dataset("dt", self.core.mu_to_seconds(
            self.core.get_rtio_counter_mu() - t0) / n)

    @kernel
    def drhold(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.cfg_drhold(0, False)
        self.dev.cfg_drhold(2, True)
        self.dev.cfg_drhold(3, True)
        self.dev.cfg_drhold_all(0b1010)

    @kernel
    def drhold_speed(self):
        self.core.break_realtime()
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.cfg_drhold(1, bool(i & 1))
        self.set_dataset("dt", self.core.mu_to_seconds(
            self.core.get_rtio_counter_mu() - t0) / n)

    @kernel
    def mask_nu(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.cfg_mask_nu(0, False)
        self.dev.cfg_mask_nu(1, True)
        self.dev.cfg_mask_nu(3, True)
        self.dev.cfg_mask_nu_all(0b1010)

    @kernel
    def mask_nu_speed(self):
        self.core.break_realtime()
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.cfg_mask_nu(2, bool(i & 1))
        self.set_dataset("dt", self.core.mu_to_seconds(
            self.core.get_rtio_counter_mu() - t0) / n)

    @kernel
    def sync(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.set_sync_div(2)

    @kernel
    def profile(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.set_profile(0, 7)
        self.dev.set_profile(0, 0)

    @kernel
    def cfg_profile(self):
        self.core.break_realtime()
        self.dev.init()
        self.dev.set_profile(0, 7)
        self.dev.set_profile(1, 0)
        self.dev.set_profile(2, 3)
        self.dev.set_profile(3, 5)
        self.dev.cfg_drctl_all(0b1111)


class UrukulTest(ExperimentCase):
    def test_instantiate(self):
        self.execute(UrukulExp, "instantiate")

    def test_init(self):
        self.execute(UrukulExp, "init")

    def test_cfg_write(self):
        self.execute(UrukulExp, "cfg_write")

    def test_sta_read(self):
        self.execute(UrukulExp, "sta_read")
        sta = self.dataset_mgr.get("sta")
        print(hex(sta))

    def test_io_rst(self):
        self.execute(UrukulExp, "io_rst")

    def test_switches(self):
        self.execute(UrukulExp, "switches")

    def test_switch_speed(self):
        self.execute(UrukulExp, "switch_speed")
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 5 * us)

    def test_switches_readback(self):
        self.execute(UrukulExp, "switches_readback")
        sw_get = urukul_sta_rf_sw(self.dataset_mgr.get("sta_get"))
        sw_set = self.dataset_mgr.get("sw_set")
        self.assertEqual(sw_get, sw_set)

    def test_att_enables(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "att_enables")

    def test_att_enable_speed(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "att_enable_speed")
            dt = self.dataset_mgr.get("dt")
            print(dt)
            self.assertLess(dt, 5 * us)

    def test_att(self):
        self.execute(UrukulExp, "att")
        att_set = self.dataset_mgr.get("att_set")
        self.assertEqual(att_set, self.dataset_mgr.get("att_get"))
        self.assertEqual(att_set, self.dataset_mgr.get("att_reg"))

    def test_att_channel(self):
        self.execute(UrukulExp, "att_channel")
        att_set = self.dataset_mgr.get("att_set")
        self.assertEqual(att_set, self.dataset_mgr.get("att_get"))
        self.assertEqual(att_set, self.dataset_mgr.get("att_reg"))

    def test_att_channel_get(self):
        self.execute(UrukulExp, "att_channel_get")
        att_set = self.dataset_mgr.get("att_set")
        self.assertListEqual(att_set, self.dataset_mgr.get("att_get"))
        att_reg = self.dataset_mgr.get("att_reg")
        for att in att_set:
            self.assertEqual(att, att_reg & 0xff)
            att_reg >>= 8

    def test_att_speed(self):
        self.execute(UrukulExp, "att_speed")
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 5 * us)

    def test_osk(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "osk")

    def test_osk_speed(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "osk_speed")
            dt = self.dataset_mgr.get("dt")
            print(dt)
            self.assertLess(dt, 5 * us)

    def test_drctl(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "drctl")

    def test_drctl_speed(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "drctl_speed")
            dt = self.dataset_mgr.get("dt")
            print(dt)
            self.assertLess(dt, 5 * us)

    def test_drhold(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "drhold")

    def test_drhold_speed(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "drhold_speed")
            dt = self.dataset_mgr.get("dt")
            print(dt)
            self.assertLess(dt, 5 * us)

    def test_mask_nu(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "mask_nu")

    def test_mask_nu_speed(self):
        if self.device_mgr.get(CPLD).proto_rev == STA_PROTO_REV_9:
            self.execute(UrukulExp, "mask_nu_speed")
            dt = self.dataset_mgr.get("dt")
            print(dt)
            self.assertLess(dt, 5 * us)

    def test_sync(self):
        self.execute(UrukulExp, "sync")

    def test_profile(self):
        self.execute(UrukulExp, "profile")
