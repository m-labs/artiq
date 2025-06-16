from numpy import int64

from artiq.coredevice.ad9910 import (
    _AD9910_REG_FTW,
    _AD9910_REG_PROFILE0,
    DEFAULT_PROFILE,
    RAM_DEST_FTW,
    RAM_MODE_RAMPUP,
)
from artiq.coredevice.urukul import (
    STA_PROTO_REV_8,
    STA_PROTO_REV_9,
    ProtoRev8,
    ProtoRev9,
    urukul_sta_smp_err,
)
from artiq.experiment import *
from artiq.test.coredevice.test_ad9910_waveform import io_update_device
from artiq.test.hardware_testbench import ExperimentCase

# Set to desired devices
CPLD = "urukul_cpld"
DDS = "urukul_ch0"


class AD9910Exp(EnvExperiment):
    def build(self, runner, io_update_device=True):
        self.setattr_device("core")
        self.cpld = self.get_device(CPLD)
        self.dev = self.get_device(DDS)
        self.runner = runner
        self.io_update_device = io_update_device

    def run(self):
        getattr(self, self.runner)()

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
    def init_fail_proto_rev(self):
        self.core.break_realtime()
        self.cpld.init()
        cfg = self.cpld.cfg_reg
        if self.cpld.proto_rev == STA_PROTO_REV_8:
            cfg &= ~(1 << ProtoRev8.CFG_CLK_SEL1)
            cfg |= 1 << ProtoRev8.CFG_CLK_SEL0
        else:
            cfg &= ~(1 << ProtoRev9.CFG_CLK_SEL1)
            cfg |= 1 << ProtoRev9.CFG_CLK_SEL0

        self.cpld.cfg_write(cfg)
        # clk_sel=1, external SMA, should fail PLL lock
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def set_get(self):
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        f = 81.2345*MHz
        p = .33
        a = .89
        att = 20*dB
        self.dev.set_att(att)
        self.dev.set(frequency=f, phase=p, amplitude=a)

        self.core.break_realtime()
        ftw, pow_, asf = self.dev.get_mu()
        self.core.break_realtime()
        att_mu = self.dev.get_att_mu()

        self.set_dataset("ftw_set", self.dev.frequency_to_ftw(f))
        self.set_dataset("ftw_get", ftw)
        self.set_dataset("pow_set", self.dev.turns_to_pow(p))
        self.set_dataset("pow_get", pow_)
        self.set_dataset("asf_set", self.dev.amplitude_to_asf(a))
        self.set_dataset("asf_get", asf)
        self.set_dataset("att_set", self.cpld.att_to_mu(att))
        self.set_dataset("att_get", att_mu)

        if not self.io_update_device:
            self.core.break_realtime()
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def set_get_io_update_regs(self):
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        f = 81.2345*MHz
        p = .33
        a = .89
        self.dev.set_frequency(f)
        self.dev.set_phase(p)
        self.dev.set_amplitude(a)
        self.dev.io_update.pulse_mu(8)

        self.core.break_realtime()
        ftw = self.dev.get_ftw()
        self.core.break_realtime()
        pow_ = self.dev.get_pow()
        self.core.break_realtime()
        asf = self.dev.get_asf()

        self.set_dataset("ftw_set", self.dev.frequency_to_ftw(f))
        self.set_dataset("ftw_get", ftw)
        self.set_dataset("pow_set", self.dev.turns_to_pow(p))
        self.set_dataset("pow_get", pow_)
        self.set_dataset("asf_set", self.dev.amplitude_to_asf(a))
        self.set_dataset("asf_get", asf)

        if not self.io_update_device:
            self.core.break_realtime()
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def read_write64(self):
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        lo = 0x12345678
        hi = 0x09abcdef
        self.dev.write64(_AD9910_REG_PROFILE0 + DEFAULT_PROFILE, hi, lo)
        self.dev.io_update.pulse_mu(8)
        read = self.dev.read64(_AD9910_REG_PROFILE0 + DEFAULT_PROFILE)
        self.set_dataset("write", (int64(hi) << 32) | lo)
        self.set_dataset("read", read)
        if not self.io_update_device:
            self.core.break_realtime()
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def set_speed(self):
        self.core.break_realtime()
        self.cpld.init()
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
        self.cpld.init()
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
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
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
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def sync_scan(self, err, win):
        for in_delay in range(len(err)):
            self.dev.set_sync(in_delay=in_delay, window=win)
            self.dev.clear_smp_err()
            # delay(10*us)  # integrate SMP_ERR statistics
            e = urukul_sta_smp_err(self.cpld.sta_read())
            err[in_delay] = (e >> (self.dev.chip_select - 4)) & 1
            delay(50*us)  # slack

    @kernel
    def io_update_delay(self):
        self.core.break_realtime()
        self.cpld.init()
        self.dev.init()
        bins1 = [0]*4
        bins2 = [0]*4
        self.scan_io_delay(bins1, bins2)
        self.set_dataset("bins1", bins1)
        self.set_dataset("bins2", bins2)
        self.set_dataset("dly", self.dev.tune_io_update_delay())

    @kernel
    def scan_io_delay(self, bins1, bins2):
        delay(100*us)
        n = 100
        for i in range(n):
            for j in range(len(bins1)):
                bins1[j] += self.dev.measure_io_update_alignment(int64(j), j + 1)
                bins2[j] += self.dev.measure_io_update_alignment(int64(j), j + 2)
        delay(10*ms)

    @kernel
    def sw_readback(self):
        self.core.break_realtime()
        self.cpld.init()
        self.dev.init()
        self.dev.cfg_sw(False)
        self.dev.sw.on()
        sw_on = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        delay(10*us)
        self.dev.sw.off()
        sw_off = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        self.set_dataset("sw", (sw_on, sw_off))

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
        delay(10*us)
        self.dev.cfg_sw(False)
        cfg_sw_off = (self.cpld.sta_read() >> (self.dev.chip_select - 4)) & 1
        self.set_dataset("cfg_sw", (cfg_sw_on, cfg_sw_off))
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.core.break_realtime()
            self.dev.cfg_mask_nu(False)

    @kernel
    def profile_readback(self):
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        for i in range(8):
            self.dev.set_mu(ftw=i, profile=i)
        ftw = [0] * 8
        for i in range(8):
            self.cpld.set_profile(self.dev.chip_select - 4, i)
            # If PROFILE is not alligned to SYNC_CLK a multi-bit change
            # doesn't transfer cleanly. Use IO_UPDATE to load the profile
            # again.
            self.dev.io_update.pulse_mu(8)
            ftw[i] = self.dev.read32(_AD9910_REG_FTW)
            delay(100*us)
        self.set_dataset("ftw", ftw)
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def ram_write(self):
        n = 1 << 10
        write = [0]*n
        for i in range(n):
            write[i] = i | (i << 16)
        read = [0]*n

        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        self.dev.set_cfr1(ram_enable=0)
        self.dev.io_update.pulse_mu(8)
        self.dev.set_profile_ram(
            start=0, end=0 + n - 1, step=1,
            profile=0, mode=RAM_MODE_RAMPUP)
        self.cpld.set_profile(self.dev.chip_select - 4, 0)
        self.dev.io_update.pulse_mu(8)
        delay(1*ms)
        self.dev.write_ram(write)
        delay(1*ms)
        self.dev.read_ram(read)
        self.set_dataset("w", write)
        self.set_dataset("r", read)
        if not self.io_update_device:
            self.core.break_realtime()
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def ram_read_overlapping(self):
        write = [0]*989
        for i in range(len(write)):
            write[i] = i
        read = [0]*100
        offset = 367

        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        self.dev.set_cfr1(ram_enable=0)
        self.dev.io_update.pulse_mu(8)

        self.dev.set_profile_ram(
            start=0, end=0 + len(write) - 1, step=1,
            profile=0, mode=RAM_MODE_RAMPUP)
        self.dev.set_profile_ram(
            start=offset, end=offset + len(read) - 1, step=1,
            profile=1, mode=RAM_MODE_RAMPUP)

        self.cpld.set_profile(self.dev.chip_select - 4, 0)
        self.dev.io_update.pulse_mu(8)
        delay(1*ms)
        self.dev.write_ram(write)
        delay(1*ms)
        self.cpld.set_profile(self.dev.chip_select - 4, 1)
        self.dev.io_update.pulse_mu(8)
        self.dev.read_ram(read)

        # RAM profile addresses are apparently aligned
        # to the last address of the RAM
        start = len(write) - offset - len(read)
        end = len(write) - offset
        self.set_dataset("w", write[start:end])
        self.set_dataset("r", read)

        if not self.io_update_device:
            self.core.break_realtime()
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def ram_exec(self):
        ftw0 = [0x12345678]*2
        ftw1 = [0x55aaaa55]*2
        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        self.dev.set_cfr1(ram_enable=0)
        self.dev.io_update.pulse_mu(8)

        self.dev.set_profile_ram(
            start=100, end=100 + len(ftw0) - 1, step=1,
            profile=3, mode=RAM_MODE_RAMPUP)
        self.dev.set_profile_ram(
            start=200, end=200 + len(ftw1) - 1, step=1,
            profile=4, mode=RAM_MODE_RAMPUP)

        self.cpld.set_profile(self.dev.chip_select - 4, 3)
        self.dev.io_update.pulse_mu(8)
        self.dev.write_ram(ftw0)

        self.cpld.set_profile(self.dev.chip_select - 4, 4)
        self.dev.io_update.pulse_mu(8)
        self.dev.write_ram(ftw1)

        self.dev.set_cfr1(ram_enable=1, ram_destination=RAM_DEST_FTW)
        self.dev.io_update.pulse_mu(8)

        self.cpld.set_profile(self.dev.chip_select - 4, 3)
        self.dev.io_update.pulse_mu(8)
        ftw0r = self.dev.read32(_AD9910_REG_FTW)
        delay(100*us)

        self.cpld.set_profile(self.dev.chip_select - 4, 4)
        self.dev.io_update.pulse_mu(8)
        ftw1r = self.dev.read32(_AD9910_REG_FTW)

        self.set_dataset("ftw", [ftw0[0], ftw0r, ftw1[0], ftw1r])

        if not self.io_update_device:
            self.core.break_realtime()
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def ram_convert_frequency(self):
        freq = [33*MHz]*2
        ram = [0]*len(freq)
        self.dev.frequency_to_ram(freq, ram)

        self.core.break_realtime()
        self.cpld.init()
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(True)
        self.dev.init()
        self.dev.set_cfr1(ram_enable=0)
        self.dev.io_update.pulse_mu(8)
        self.dev.set_profile_ram(
            start=100, end=100 + len(ram) - 1, step=1,
            profile=6, mode=RAM_MODE_RAMPUP)
        self.cpld.set_profile(self.dev.chip_select - 4, 6)
        self.dev.io_update.pulse_mu(8)
        self.dev.write_ram(ram)
        self.dev.set_cfr1(ram_enable=1, ram_destination=RAM_DEST_FTW)
        self.dev.io_update.pulse_mu(8)
        ftw_read = self.dev.read32(_AD9910_REG_FTW)
        self.set_dataset("ram", ram)
        self.set_dataset("ftw_read", ftw_read)
        self.set_dataset("freq", freq)
        if not self.io_update_device:
            self.core.break_realtime()
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dev.cfg_mask_nu(False)

    @kernel
    def ram_convert_powasf(self):
        amplitude = [.1, .9]
        turns = [.3, .5]
        ram = [0]*2
        self.dev.turns_amplitude_to_ram(turns, amplitude, ram)
        self.set_dataset("amplitude", amplitude)
        self.set_dataset("turns", turns)
        self.set_dataset("ram", ram)


class AD9910Test(ExperimentCase):
    def test_instantiate(self):
        self.execute(AD9910Exp, "instantiate")

    @io_update_device(CPLD, True, False)
    def test_init(self, io_update_device):
        self.execute(AD9910Exp, "init", io_update_device=io_update_device)

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_8)
    def test_init_fail_proto_rev8(self, io_update_device):
        with self.assertRaises(ValueError):
            self.execute(
                AD9910Exp, "init_fail_proto_rev", io_update_device=io_update_device
            )

    @io_update_device(CPLD, True, False)
    def test_set_get(self, io_update_device):
        self.execute(AD9910Exp, "set_get", io_update_device)
        for attr in ["ftw", "pow", "asf", "att"]:
            with self.subTest(attribute=attr):
                get = self.dataset_mgr.get("{}_get".format(attr))
                set_ = self.dataset_mgr.get("{}_set".format(attr))
                self.assertEqual(get, set_)

    @io_update_device(CPLD, True, False)
    def test_set_get_io_update_regs(self, io_update_device):
        self.execute(
            AD9910Exp, "set_get_io_update_regs", io_update_device=io_update_device
        )
        for attr in ["ftw", "pow", "asf"]:
            with self.subTest(attribute=attr):
                get = self.dataset_mgr.get("{}_get".format(attr))
                set_ = self.dataset_mgr.get("{}_set".format(attr))
                self.assertEqual(get, set_)

    @io_update_device(CPLD, True, False)
    def test_read_write64(self, io_update_device):
        self.execute(AD9910Exp, "read_write64", io_update_device=io_update_device)
        write = self.dataset_mgr.get("write")
        read = self.dataset_mgr.get("read")
        self.assertEqual(hex(write), hex(read))

    @io_update_device(CPLD, True)
    def test_set_speed(self, io_update_device):
        self.execute(AD9910Exp, "set_speed", io_update_device=io_update_device)
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 70 * us)

    @io_update_device(CPLD, True)
    def test_set_speed_mu(self, io_update_device):
        self.execute(AD9910Exp, "set_speed_mu", io_update_device=io_update_device)
        dt = self.dataset_mgr.get("dt")
        print(dt)
        self.assertLess(dt, 11 * us)

    @io_update_device(CPLD, True, False)
    def test_sync_window(self, io_update_device):
        # Assume sync_div is not zero
        if "sync_device" in self.device_mgr.get_desc(DDS):
            self.execute(AD9910Exp, "sync_window", io_update_device=io_update_device)
            err = self.dataset_mgr.get("err")
            dly = self.dataset_mgr.get("dly")
            win = self.dataset_mgr.get("win")
            print(dly, win, err)
            # make sure one tap margin on either side of optimal delay
            for i in -1, 0, 1:
                self.assertEqual(err[i + dly], 0)

    @io_update_device(CPLD, True)
    def test_io_update_delay(self, io_update_device):
        self.execute(AD9910Exp, "io_update_delay", io_update_device=io_update_device)
        dly = self.dataset_mgr.get("dly")
        bins1 = self.dataset_mgr.get("bins1")
        bins2 = self.dataset_mgr.get("bins2")
        print(dly, bins1, bins2)
        n = max(bins2)
        # no edge at optimal delay
        self.assertEqual(bins2[(dly + 1) & 3], 0)
        # many edges near expected position
        self.assertGreater(bins2[(dly + 3) & 3], n * 0.9)

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_8)
    def test_sw_readback(self, io_update_device):
        if "sw_device" in self.device_mgr.get_desc(DDS).get("arguments", []):
            self.execute(AD9910Exp, "sw_readback", io_update_device=io_update_device)
            self.assertEqual(self.dataset_mgr.get("sw"), (1, 0))

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_cfg_sw_readback(self, io_update_device):
        self.execute(AD9910Exp, "cfg_sw_readback", io_update_device=io_update_device)
        self.assertEqual(self.dataset_mgr.get("cfg_sw"), (1, 0))

    @io_update_device(True, False)
    def test_profile_readback(self, io_update_device):
        self.execute(AD9910Exp, "profile_readback", io_update_device=io_update_device)
        self.assertEqual(self.dataset_mgr.get("ftw"), list(range(8)))

    @io_update_device(CPLD, True, False)
    def test_ram_write(self, io_update_device):
        self.execute(AD9910Exp, "ram_write", io_update_device=io_update_device)
        read = self.dataset_mgr.get("r")
        write = self.dataset_mgr.get("w")
        self.assertEqual(len(read), len(write))
        self.assertEqual(read, write)

    @io_update_device(CPLD, True, False)
    def test_ram_read_overlapping(self, io_update_device):
        self.execute(
            AD9910Exp, "ram_read_overlapping", io_update_device=io_update_device
        )
        read = self.dataset_mgr.get("r")
        write = self.dataset_mgr.get("w")
        self.assertEqual(len(read), 100)
        self.assertEqual(read, write)

    @io_update_device(CPLD, True, False)
    def test_ram_exec(self, io_update_device):
        self.execute(AD9910Exp, "ram_exec", io_update_device=io_update_device)
        ftw = self.dataset_mgr.get("ftw")
        self.assertEqual(ftw[0], ftw[1])
        self.assertEqual(ftw[2], ftw[3])

    @io_update_device(CPLD, True, False)
    def test_ram_convert_frequency(self, io_update_device):
        exp = self.execute(
            AD9910Exp, "ram_convert_frequency", io_update_device=io_update_device
        )
        ram = self.dataset_mgr.get("ram")
        ftw_read = self.dataset_mgr.get("ftw_read")
        self.assertEqual(ftw_read, ram[0])
        freq = self.dataset_mgr.get("freq")
        self.assertEqual(ftw_read, exp.dev.frequency_to_ftw(freq[0]))
        self.assertAlmostEqual(freq[0], exp.dev.ftw_to_frequency(ftw_read), delta=0.25)

    @io_update_device(CPLD, True, False)
    def test_ram_convert_powasf(self, io_update_device):
        exp = self.execute(
            AD9910Exp, "ram_convert_powasf", io_update_device=io_update_device
        )
        ram = self.dataset_mgr.get("ram")
        amplitude = self.dataset_mgr.get("amplitude")
        turns = self.dataset_mgr.get("turns")
        for i in range(len(ram)):
            self.assertEqual((ram[i] >> 16) & 0xFFFF, exp.dev.turns_to_pow(turns[i]))
            self.assertEqual((ram[i] >> 2) & 0x3FFF, exp.dev.amplitude_to_asf(amplitude[i]))
