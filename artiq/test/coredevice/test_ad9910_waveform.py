from functools import wraps

import artiq.coredevice.spi2 as spi
from artiq.coredevice.ad9910 import (
    _AD9910_REG_ASF,
    _AD9910_REG_RAMP_LIMIT,
    _AD9910_REG_RAMP_RATE,
    _AD9910_REG_RAMP_STEP,
)
from artiq.coredevice.urukul import STA_PROTO_REV_8, STA_PROTO_REV_9
from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase

###############################################################################
## NOTE: These test are intended to create waveforms from AD9910 Urukul boards
## (all protocol revisions, see tests below) used with an oscilloscope.
## Set your oscilloscope to:
##
## Time division: 2 ns
## Voltage division: 500 mV
##
## These settings work with a nominal 100 MHz waveform.
## You will need to play with your trigger level setting for some of the tests.
##
## If you change FREQ (see below) to something else, adjust your oscilloscope
## settings to accomodate.
###############################################################################

FREQ = 100 * MHz
AMP = 1.0
ATT = 1.0

# Set to desired devices
CPLD = "urukul0_cpld"
DDS1 = "urukul0_ch0"
DDS2 = "urukul0_ch3"


class AD9910WaveformExp(EnvExperiment):
    def build(self, runner, io_update_device=True):
        self.setattr_device("core")
        self.cpld = self.get_device(CPLD)
        self.dds1 = self.get_device(DDS1)
        self.dds2 = self.get_device(DDS2)
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
        self.dds1.init()
        self.dds2.init()

    @kernel
    def single_tone(self):
        self.core.reset()
        self.cpld.init()

        # Set ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dds1.cfg_att_en(True)
            self.dds2.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)
            self.dds2.cfg_mask_nu(True)

        self.dds1.init()
        self.dds2.init()

        delay(10 * ms)

        self.dds1.set(FREQ, amplitude=AMP)
        self.dds2.set(FREQ, amplitude=AMP)

        # Switch on waveforms
        self.dds1.cfg_sw(True)
        self.dds2.cfg_sw(True)

        self.dds1.set_att(ATT)
        self.dds2.set_att(ATT)

        delay(5 * s)

        # Switch off waveforms
        self.dds1.cfg_sw(False)
        self.dds2.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)
            self.dds2.cfg_mask_nu(False)

        # UnSet ATT_EN
        if self.cpld.proto_rev == STA_PROTO_REV_9:
            self.dds1.cfg_att_en(False)
            self.dds2.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def toggle_profile(self):
        self.core.reset()
        self.cpld.init()

        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)
            self.dds2.cfg_mask_nu(True)

        self.dds1.init()
        self.dds2.init()

        delay(10 * ms)

        ## SET SINGLE-TONE PROFILES
        # Set Profile 7 (default)
        self.dds1.set(FREQ, amplitude=AMP)
        self.dds2.set(FREQ, amplitude=AMP)
        # Set Profile 6 (default)
        self.dds1.set(FREQ + 25 * MHz, amplitude=AMP, profile=6)
        self.dds2.set(FREQ + 25 * MHz, amplitude=AMP, profile=6)
        # Set Profile 5 (default)
        self.dds1.set(FREQ + 50 * MHz, amplitude=AMP, profile=5)
        self.dds2.set(FREQ + 50 * MHz, amplitude=AMP, profile=5)
        # Set Profile 4 (default)
        self.dds1.set(FREQ + 75 * MHz, amplitude=AMP, profile=4)
        self.dds2.set(FREQ + 75 * MHz, amplitude=AMP, profile=4)

        delay(1 * s)  # slack

        # Set Profile 3 (default)
        self.dds1.set(FREQ + FREQ, amplitude=AMP, profile=3)
        self.dds2.set(FREQ + FREQ, amplitude=AMP, profile=3)
        # Set Profile 2 (default)
        self.dds1.set(FREQ + 125 * MHz, amplitude=AMP, profile=2)
        self.dds2.set(FREQ + 125 * MHz, amplitude=AMP, profile=2)
        # Set Profile 1 (default)
        self.dds1.set(FREQ + 150 * MHz, amplitude=AMP, profile=1)
        self.dds2.set(FREQ + 150 * MHz, amplitude=AMP, profile=1)
        # Set Profile 0 (default)
        self.dds1.set(FREQ + 175 * MHz, amplitude=AMP, profile=0)
        self.dds2.set(FREQ + 175 * MHz, amplitude=AMP, profile=0)

        # Switch on waveforms -- Profile 7 (default)
        self.dds1.cfg_sw(True)
        self.dds2.cfg_sw(True)
        self.dds1.set_att(ATT)
        self.dds2.set_att(ATT)
        delay(2 * s)
        # Switch off waveforms
        self.dds1.cfg_sw(False)
        self.dds2.cfg_sw(False)

        # Iterate over Profiles 6 to 0
        for i in range(6, -1, -1):
            # Switch channels 0 and 3 to Profile i
            self.cpld.set_profile(0, i)
            # This is the main different between proto_rev's,
            # one sets them all
            # self.cpld.set_profile(3, i)
            self.dds1.cfg_sw(True)
            self.dds2.cfg_sw(True)
            delay(2 * s)
            # Switch off waveforms
            self.dds1.cfg_sw(False)
            self.dds2.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)
            self.dds2.cfg_mask_nu(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def toggle_profiles(self):
        self.core.reset()
        self.cpld.init()
        # Set ATT_EN
        self.dds1.cfg_att_en(True)
        self.dds2.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)
            self.dds2.cfg_mask_nu(True)

        self.dds1.init()
        self.dds2.init()

        delay(10 * ms)

        ## SET SINGLE-TONE PROFILES
        # Set Profile 7 (default)
        self.dds1.set(FREQ, amplitude=AMP)
        self.dds2.set(FREQ, amplitude=AMP)
        # Set Profile 6 (default)
        self.dds1.set(FREQ + 25 * MHz, amplitude=AMP, profile=6)
        self.dds2.set(FREQ + 25 * MHz, amplitude=AMP, profile=6)
        # Set Profile 5 (default)
        self.dds1.set(FREQ + 50 * MHz, amplitude=AMP, profile=5)
        self.dds2.set(FREQ + 50 * MHz, amplitude=AMP, profile=5)
        # Set Profile 4 (default)
        self.dds1.set(FREQ + 75 * MHz, amplitude=AMP, profile=4)
        self.dds2.set(FREQ + 75 * MHz, amplitude=AMP, profile=4)

        delay(1 * s)  # slack

        # Set Profile 3 (default)
        self.dds1.set(FREQ + FREQ, amplitude=AMP, profile=3)
        self.dds2.set(FREQ + FREQ, amplitude=AMP, profile=3)
        # Set Profile 2 (default)
        self.dds1.set(FREQ + 125 * MHz, amplitude=AMP, profile=2)
        self.dds2.set(FREQ + 125 * MHz, amplitude=AMP, profile=2)
        # Set Profile 1 (default)
        self.dds1.set(FREQ + 150 * MHz, amplitude=AMP, profile=1)
        self.dds2.set(FREQ + 150 * MHz, amplitude=AMP, profile=1)
        # Set Profile 0 (default)
        self.dds1.set(FREQ + 175 * MHz, amplitude=AMP, profile=0)
        self.dds2.set(FREQ + 175 * MHz, amplitude=AMP, profile=0)

        # Switch on waveforms -- Profile 7 (default)
        self.dds1.cfg_sw(True)
        self.dds2.cfg_sw(True)
        self.dds1.set_att(ATT)
        self.dds2.set_att(ATT)
        delay(2 * s)
        # Switch off waveforms
        self.dds1.cfg_sw(False)
        self.dds2.cfg_sw(False)

        # Iterate over Profiles 6 to 0
        for i in range(6, -1, -1):
            # Switch channels 0 and 3 to Profile i
            self.cpld.set_profile(0, i)
            self.cpld.set_profile(3, i)
            self.dds1.cfg_sw(True)
            self.dds2.cfg_sw(True)
            delay(2 * s)
            # Switch off waveforms
            self.dds1.cfg_sw(False)
            self.dds2.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)
            self.dds2.cfg_mask_nu(False)

        # UnSet ATT_EN
        self.dds1.cfg_att_en(False)
        self.dds2.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def osk(self):
        self.core.reset()
        self.cpld.init()
        # Set ATT_EN
        self.dds1.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)

        self.dds1.init()

        delay(10 * ms)

        self.dds1.set(FREQ, amplitude=AMP)
        self.dds1.set_cfr1(manual_osk_external=1, osk_enable=1)
        self.dds1.cpld.io_update.pulse(1 * ms)
        self.dds1.set_asf(0x3FFF)
        self.dds1.cpld.io_update.pulse(1 * ms)

        # Switch on waveform, then set attenuation
        self.dds1.cfg_sw(True)
        self.dds1.set_att(ATT)
        for _ in range(5):
            # Toggle output via OSK
            self.dds1.cfg_osk(True)
            delay(1 * s)
            self.dds1.cfg_osk(False)
            delay(1 * s)
        # Switch off waveform
        self.dds1.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)

        # UnSet ATT_EN
        self.dds1.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def osk_auto(self):
        self.core.reset()
        self.cpld.init()
        # Set ATT_EN
        self.dds1.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)

        self.dds1.init()

        delay(10 * ms)

        self.dds1.set(FREQ, amplitude=AMP)
        self.dds1.set_cfr1(osk_enable=1, select_auto_osk=1)
        self.dds1.cpld.io_update.pulse(1 * ms)
        self.dds1.write32(_AD9910_REG_ASF, 0xFFFF << 16 | 0x3FFF << 2 | 0b11)
        self.dds1.cpld.io_update.pulse(1 * ms)

        # Switch on waveform, then set attenuation
        self.dds1.cfg_sw(True)
        self.dds1.set_att(ATT)
        for _ in range(5):
            self.dds1.cfg_osk(True)
            delay(1 * s)
            self.dds1.cfg_osk(False)
            delay(1 * s)
        # Switch off waveform
        self.dds1.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)

        # UnSet ATT_EN
        self.dds1.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def drg_normal(self):
        self.core.reset()
        self.cpld.init()
        # Set ATT_EN
        self.dds1.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)

        self.dds1.init()

        delay(10 * ms)

        self.dds1.frequency_to_ftw(FREQ)
        # cfr2 21:20 destination, 19 drg enable, no-dwell high, no-dwell low,
        self.dds1.set(FREQ, amplitude=AMP)
        self.dds1.set_cfr2(drg_enable=1)
        self.dds1.cpld.io_update.pulse(1 * ms)
        self.dds1.write64(
            _AD9910_REG_RAMP_LIMIT,
            self.dds1.frequency_to_ftw(FREQ + 30 * MHz),
            self.dds1.frequency_to_ftw(FREQ - 30 * MHz),
        )
        # The larger the values, the slower the update happens
        self.dds1.write32(_AD9910_REG_RAMP_RATE, 0x004F004F)
        # The smaller the value it is, the smaller the frequency step
        self.dds1.write64(_AD9910_REG_RAMP_STEP, 0xF0, 0xF0)
        self.dds1.cpld.io_update.pulse(1 * ms)

        # Switch on waveform, then set attenuation
        self.dds1.cfg_sw(True)
        self.dds1.set_att(ATT)
        for _ in range(10):
            self.dds1.cfg_drctl(True)
            delay(0.5 * s)
            self.dds1.cfg_drctl(False)
            delay(0.5 * s)
        # Switch off waveform
        self.dds1.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)

        # UnSet ATT_EN
        self.dds1.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def drg_normal_with_hold(self):
        self.core.reset()
        self.cpld.init()
        # Set ATT_EN
        self.dds1.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)

        self.dds1.init()

        delay(10 * ms)

        self.dds1.frequency_to_ftw(FREQ)
        # cfr2 21:20 destination, 19 drg enable, no-dwell high, no-dwell low,
        self.dds1.set(FREQ, amplitude=AMP)
        self.dds1.set_cfr2(drg_enable=1)
        self.dds1.cpld.io_update.pulse(1 * ms)
        self.dds1.write64(
            _AD9910_REG_RAMP_LIMIT,
            self.dds1.frequency_to_ftw(FREQ + 30 * MHz),
            self.dds1.frequency_to_ftw(FREQ - 30 * MHz),
        )
        # The larger the values, the slower the update happens
        self.dds1.write32(_AD9910_REG_RAMP_RATE, 0x004F004F)
        # The smaller the value it is, the smaller the frequency step
        self.dds1.write64(_AD9910_REG_RAMP_STEP, 0xF0, 0xF0)
        self.dds1.cpld.io_update.pulse(1 * ms)

        # Switch on waveform, then set attenuation
        self.dds1.cfg_sw(True)
        self.dds1.set_att(ATT)
        for _ in range(10):
            self.dds1.cfg_drctl(True)
            delay(0.25 * s)
            self.dds1.cfg_drhold(True)
            delay(0.25)
            self.dds1.cfg_drhold(False)
            delay(0.25)
            self.dds1.cfg_drctl(False)
            delay(0.25)
            self.dds1.cfg_drhold(True)
            delay(0.25)
            self.dds1.cfg_drhold(False)
            delay(0.25)
        # Switch off waveform
        self.dds1.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)

        # UnSet ATT_EN
        self.dds1.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def drg_nodwell(self):
        self.core.reset()
        self.cpld.init()
        # Set ATT_EN
        self.dds1.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)

        self.dds1.init()

        delay(10 * ms)

        self.dds1.frequency_to_ftw(FREQ)
        # cfr2 21:20 destination, 19 drg enable, no-dwell high, no-dwell low,
        self.dds1.set(FREQ, amplitude=AMP)
        self.dds1.set_cfr2(drg_enable=1, drg_nodwell_high=1, drg_nodwell_low=1)
        self.dds1.cpld.io_update.pulse(1 * ms)
        self.dds1.write64(
            _AD9910_REG_RAMP_LIMIT,
            self.dds1.frequency_to_ftw(FREQ + 30 * MHz),
            self.dds1.frequency_to_ftw(FREQ - 30 * MHz),
        )
        # The larger the values, the slower the update happens
        self.dds1.write32(_AD9910_REG_RAMP_RATE, 0x004F004F)
        # The smaller the value it is, the smaller the frequency step
        self.dds1.write64(_AD9910_REG_RAMP_STEP, 0xF0, 0xF0)
        self.dds1.cpld.io_update.pulse(1 * ms)

        # Switch on waveform, then set attenuation
        self.dds1.cfg_sw(True)
        self.dds1.set_att(ATT)

        delay(10 * s)
        # Switch off waveform
        self.dds1.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)

        # UnSet ATT_EN
        self.dds1.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())

    @kernel
    def att_single_tone(self):
        self.core.reset()
        self.cpld.init()
        # Set ATT_EN
        self.dds1.cfg_att_en(True)
        self.dds2.cfg_att_en(True)
        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)
            self.dds2.cfg_mask_nu(True)

        self.dds1.init()
        self.dds2.init()

        delay(10 * ms)

        self.dds1.set(FREQ, amplitude=AMP)
        self.dds2.set(FREQ, amplitude=AMP)

        delay(1 * ms)

        # Switch on waveforms
        self.dds1.cfg_sw(True)
        self.dds2.cfg_sw(True)

        # This must be set AFTER cfg_sw set to True (why?)
        self.dds1.set_att(0.0 * dB)
        self.dds2.set_att(0.0 * dB)

        delay(5 * s)

        self.dds1.set_att(10.0)
        self.dds2.set_att(10.0)

        delay(5 * s)

        self.dds1.set_att(20.0)
        self.dds2.set_att(20.0)

        delay(5 * s)

        self.dds1.set_att(30.0)
        self.dds2.set_att(30.0)

        delay(5 * s)

        # Switch off waveforms
        self.dds1.cfg_sw(False)
        self.dds2.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)
            self.dds2.cfg_mask_nu(False)

        # UnSet ATT_EN
        self.dds1.cfg_att_en(False)
        self.dds2.cfg_att_en(False)

        self.core.wait_until_mu(now_mu())


def io_update_device(required, proto_rev=None):
    """
    Decorator to mark whether a test requires 'io_update_device' to be set or unset
    and optionally check the protocol version.
    """

    def decorator(test_func):
        @wraps(test_func)
        def wrapper(self, *args, **kwargs):
            if hasattr(self.device_mgr, "get_desc"):
                if (
                    required
                    and "io_update_device"
                    not in self.device_mgr.get_desc(CPLD)["arguments"]
                ):
                    self.skipTest("This test requires 'io_update_device' to be set.")
                if (
                    not required
                    and "io_update_device"
                    in self.device_mgr.get_desc(CPLD)["arguments"]
                ):
                    self.skipTest("This test requires 'io_update_device' to be unset.")

            if proto_rev is not None:
                actual_proto_rev = self.device_mgr.get(CPLD).proto_rev
                if actual_proto_rev != proto_rev:
                    self.skipTest(
                        f"This test requires proto_rev={proto_rev}, but the current proto_rev is {actual_proto_rev}."
                    )

            print(f"Running test: {test_func.__name__}")
            return test_func(self, *args, **kwargs)

        wrapper.requires_io_update_device = required
        return wrapper

    return decorator


class AD9910Test(ExperimentCase):
    def test_instantiate(self):
        self.execute(AD9910WaveformExp, "instantiate")

    def test_init(self):
        self.execute(AD9910WaveformExp, "init")

    @io_update_device(True)
    def test_single_tone(self):
        self.execute(AD9910WaveformExp, "single_tone")

    @io_update_device(False)
    def test_single_tone_no_io_update_device(self):
        self.execute(AD9910WaveformExp, "single_tone", io_update_device=False)

    @io_update_device(True, proto_rev=STA_PROTO_REV_8)
    def test_toggle_profile(self):
        self.execute(AD9910WaveformExp, "toggle_profile")

    @io_update_device(False, proto_rev=STA_PROTO_REV_8)
    def test_toggle_profile_no_io_update_device(self):
        self.execute(AD9910WaveformExp, "toggle_profile", io_update_device=False)

    @io_update_device(True, proto_rev=STA_PROTO_REV_9)
    def test_toggle_profiles(self):
        self.execute(AD9910WaveformExp, "toggle_profiles")

    @io_update_device(False, proto_rev=STA_PROTO_REV_9)
    def test_toggle_profiles_no_io_update_device(self):
        self.execute(AD9910WaveformExp, "toggle_profiles", io_update_device=False)

    @io_update_device(True, proto_rev=STA_PROTO_REV_9)
    def test_osk(self):
        self.execute(AD9910WaveformExp, "osk")

    @io_update_device(False, proto_rev=STA_PROTO_REV_9)
    def test_osk_no_io_update_device(self):
        self.execute(AD9910WaveformExp, "osk", io_update_device=False)

    @io_update_device(True, proto_rev=STA_PROTO_REV_9)
    def test_osk_auto(self):
        self.execute(AD9910WaveformExp, "osk_auto")

    @io_update_device(False, proto_rev=STA_PROTO_REV_9)
    def test_osk_auto_no_io_update_device(self):
        self.execute(AD9910WaveformExp, "osk_auto", io_update_device=False)

    @io_update_device(True, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal(self):
        self.execute(AD9910WaveformExp, "drg_normal")

    @io_update_device(False, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal_no_io_update_device(self):
        self.execute(AD9910WaveformExp, "drg_normal", io_update_device=False)

    @io_update_device(True, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal_with_hold(self):
        self.execute(AD9910WaveformExp, "drg_normal_with_hold")

    @io_update_device(False, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal_with_hold_no_io_update_device(self):
        self.execute(AD9910WaveformExp, "drg_normal_with_hold", io_update_device=False)

    @io_update_device(True, proto_rev=STA_PROTO_REV_9)
    def test_drg_nodwell(self):
        self.execute(AD9910WaveformExp, "drg_nodwell")

    @io_update_device(False, proto_rev=STA_PROTO_REV_9)
    def test_drg_nodwell_no_io_update_device(self):
        self.execute(AD9910WaveformExp, "drg_nodwell", io_update_device=False)

    @io_update_device(True, proto_rev=STA_PROTO_REV_9)
    def test_att_single_tone(self):
        self.execute(AD9910WaveformExp, "att_single_tone")

    @io_update_device(False, proto_rev=STA_PROTO_REV_9)
    def test_att_single_tone_no_io_update_device(self):
        self.execute(AD9910WaveformExp, "att_single_tone", io_update_device=False)
