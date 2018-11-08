from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.coredevice.ad9910 import _AD9910_REG_FTW
from artiq.coredevice.urukul import (
        urukul_sta_smp_err, CFG_CLK_SEL0, CFG_CLK_SEL1)


class AD9910Exp(EnvExperiment):
    def build(self, runner):
        self.setattr_device("core")
        self.dev = self.get_device("urukul_ad9910")
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
    def init_fail(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        cfg = self.dev.cpld.cfg_reg
        cfg &= ~(1 << CFG_CLK_SEL1)
        cfg |= 1 << CFG_CLK_SEL0
        self.dev.cpld.cfg_write(cfg)
        # clk_sel=1, external SMA, should fail PLL lock
        self.dev.init()

    @kernel
    def set_get(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        self.dev.init()
        self.dev.set_att(20*dB)
        f = 81.2345*MHz
        self.dev.set(frequency=f, phase=.33, amplitude=.89)
        self.set_dataset("ftw_set", self.dev.frequency_to_ftw(f))
        self.set_dataset("ftw_get", self.dev.read32(_AD9910_REG_FTW))

    @kernel
    def set_speed(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        self.dev.init()
        f = 81.2345*MHz
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.set(frequency=f, phase=.33, amplitude=.89)
        self.set_dataset("dt", self.core.mu_to_seconds(
            self.core.get_rtio_counter_mu() - t0)/n)

    @kernel
    def set_speed_mu(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        self.dev.init()
        n = 10
        t0 = self.core.get_rtio_counter_mu()
        for i in range(n):
            self.dev.set_mu(0x12345678, 0x1234, 0x4321)
        self.set_dataset("dt", self.core.mu_to_seconds(
            self.core.get_rtio_counter_mu() - t0)/n)

    @kernel
    def sync_window(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        self.dev.init()
        err = [0] * 32
        for i in range(6):
            self.sync_scan(err, win=i)
            print(err)
            self.core.break_realtime()
        dly, win = self.dev.tune_sync_delay()
        self.sync_scan(err, win=win)
        # FIXME: win + 1  # tighten window by 2*75ps
        # after https://github.com/sinara-hw/Urukul/issues/16
        self.set_dataset("dly", dly)
        self.set_dataset("win", win)
        self.set_dataset("err", err)

    @kernel
    def sync_scan(self, err, win):
        for in_delay in range(len(err)):
            self.dev.set_sync(in_delay=in_delay, window=win)
            self.dev.clear_smp_err()
            # delay(10*us)  # integrate SMP_ERR statistics
            e = urukul_sta_smp_err(self.dev.cpld.sta_read())
            err[in_delay] = (e >> (self.dev.chip_select - 4)) & 1
            delay(50*us)  # slack

    @kernel
    def io_update_delay(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        self.dev.init()
        bins = [0]*8
        self.scan_io_delay(bins)
        self.set_dataset("bins", bins)
        self.set_dataset("dly", self.dev.io_update_delay)

    @kernel
    def scan_io_delay(self, bins):
        delay(100*us)
        n = 100
        for i in range(n):
            for phase in range(len(bins)):
                bins[phase] += self.dev.measure_io_update_alignment(phase)
        delay(10*ms)

    @kernel
    def sw_readback(self):
        self.core.break_realtime()
        self.dev.cpld.init()
        self.dev.init()
        self.dev.cfg_sw(0)
        self.dev.sw.on()
        sw_on = (self.dev.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        delay(10*us)
        self.dev.sw.off()
        sw_off = (self.dev.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        self.set_dataset("sw", (sw_on, sw_off))


class AD9910Test(ExperimentCase):
    def test_instantiate(self):
        self.execute(AD9910Exp, "instantiate")

    def test_init(self):
        self.execute(AD9910Exp, "init")

    def test_init_fail(self):
        with self.assertRaises(ValueError):
            self.execute(AD9910Exp, "init_fail")

    def test_set_get(self):
        self.execute(AD9910Exp, "set_get")
        ftw_get = self.dataset_mgr.get("ftw_get")
        ftw_set = self.dataset_mgr.get("ftw_set")
        self.assertEqual(ftw_get, ftw_set)

    def test_set_speed(self):
        self.execute(AD9910Exp, "set_speed")
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 70*us)

    def test_set_speed_mu(self):
        self.execute(AD9910Exp, "set_speed_mu")
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 10*us)

    def test_sync_window(self):
        self.execute(AD9910Exp, "sync_window")
        err = self.dataset_mgr.get("err")
        dly = self.dataset_mgr.get("dly")
        win = self.dataset_mgr.get("win")
        print(dly, win, err)
        # make sure one tap margin on either side of optimal delay
        for i in -1, 0, 1:
            self.assertEqual(err[i + dly], 0)

    def test_io_update_delay(self):
        self.execute(AD9910Exp, "io_update_delay")
        dly = self.dataset_mgr.get("dly")
        bins = self.dataset_mgr.get("bins")
        print(dly, bins)
        n = max(bins)
        # test for 4-periodicity (SYNC_CLK) and maximal contrast
        for i in range(len(bins)):
            self.assertEqual(abs(bins[i] - bins[(i + 4) % 8]), n)

    def test_sw_readback(self):
        self.execute(AD9910Exp, "sw_readback")
        self.assertEqual(self.dataset_mgr.get("sw"), (1, 0))
