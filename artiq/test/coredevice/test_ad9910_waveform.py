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

####################################################################################
## NOTE: These test are intended to create waveforms from AD9910 Urukul boards used
## with an oscilloscope (2 channels).  Most tests are for proto_rev = 0x09+.
##
## Set your oscilloscope to:
##
## Time division: 2 ns
## Voltage division: 500 mV
##
## The settings below work with a nominal 100 MHz waveform.  Set trigger to DDS1.
## You will need to play with your trigger level setting for some of the tests.
##
## If you change FREQ (see below) to something else, adjust your oscilloscope
## settings to accomodate.
####################################################################################

FREQ = 100 * MHz
AMP = 1.0
ATT = 1.0

# Set to desired devices
CPLD = "urukul1_cpld"
DDS1 = "urukul1_ch0"
DDS2 = "urukul1_ch3"


def io_update_device(cpld, *required_values, proto_rev=None):
    """
    Decorator to mark whether a test requires 'io_update_device' to be set or unset
    for a given Urukul and optionally check the protocol version.

    Parameters:
    - device_key: The key identifying the device to check.
    - *required_values: Boolean values indicating whether 'io_update_device' should be present.
    - proto_rev (optional): The required protocol revision; the test will be skipped if it does not match.
    """

    def decorator(test_func):
        @wraps(test_func)
        def wrapper(self, *args, **kwargs):
            for required in required_values:
                with self.subTest(io_update_device=required):
                    desc = (
                        self.device_mgr.get_desc(cpld)
                        if hasattr(self.device_mgr, "get_desc")
                        else {}
                    )
                    io_update_present = "io_update_device" in desc.get("arguments", [])

                    if io_update_present != required:
                        self.skipTest(
                            f"This test requires 'io_update_device' to be {required}."
                        )

                    if proto_rev is not None:
                        actual_proto_rev = self.device_mgr.get(cpld).proto_rev
                        if actual_proto_rev != proto_rev:
                            self.skipTest(
                                f"This test requires proto_rev={proto_rev}, "
                                "but the current proto_rev is {actual_proto_rev}."
                            )

                    print(
                        f"Running test: {test_func.__name__} (io_update_device={required})"
                    )
                    test_func(self, *args, **kwargs, io_update_device=required)

        return wrapper

    return decorator


class AD9910WaveformExp(EnvExperiment):
    def build(
        self,
        runner,
        io_update_device=True,
        multiple_profiles=True,
        osk_manual=True,
        drg_destination=0x0,
        use_dds2=False,
        with_hold=False,
        nodwell=0,
    ):
        self.setattr_device("core")
        self.cpld = self.get_device(CPLD)
        self.dds1 = self.get_device(DDS1)
        self.dds2 = self.get_device(DDS2)
        self.runner = runner
        self.io_update_device = io_update_device
        self.multiple_profiles = multiple_profiles
        self.osk_manual = osk_manual
        self.drg_destination = drg_destination
        self.use_dds2 = use_dds2
        self.with_hold = with_hold
        self.nodwell = nodwell

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
            self.dds1.cfg_mask_nu(True)
            self.dds2.cfg_mask_nu(True)
        self.dds1.init()
        self.dds2.init()
        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)
            self.dds2.cfg_mask_nu(False)

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
        # Set profiles from 7 to 0
        frequencies = [
            0.0,
            25 * MHz,
            50 * MHz,
            75 * MHz,
            100 * MHz,
            125 * MHz,
            150 * MHz,
            175 * MHz,
        ]
        for i in range(6, -1, -1):
            freq_offset = frequencies[i]
            profile = 7 - i
            self.dds1.set(FREQ + freq_offset, amplitude=AMP, profile=profile)
            self.dds2.set(FREQ + freq_offset, amplitude=AMP, profile=profile)
            delay(0.5 * s)  # slack

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
            # Switch channels to Profile i
            self.cpld.set_profile(0, i)
            if self.multiple_profiles:
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

        if self.osk_manual:
            self.dds1.set_cfr1(manual_osk_external=1, osk_enable=1)
        else:
            self.dds1.write32(_AD9910_REG_ASF, 0xFFFF << 16 | 0x3FFF << 2 | 0b11)
            self.dds1.set_cfr1(osk_enable=1, select_auto_osk=1)

        self.dds1.io_update.pulse(1 * ms)

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
    def drg(self):
        self.core.reset()
        self.cpld.init()

        # Set ATT_EN
        self.dds1.cfg_att_en(True)
        if self.use_dds2:
            self.dds2.cfg_att_en(True)

        if not self.io_update_device:
            # Set MASK_NU to trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(True)
            if self.use_dds2:
                self.dds2.cfg_mask_nu(True)

        self.dds1.init()
        if self.use_dds2:
            self.dds2.init()

        delay(10 * ms)

        # Set initial frequency and amplitude
        self.dds1.set(FREQ, amplitude=AMP)
        if self.use_dds2:
            self.dds2.set(FREQ, amplitude=AMP)

        # Configure DRG
        if self.drg_destination == 0x0:  # Frequency
            ramp_limit_high = self.dds1.frequency_to_ftw(FREQ + 30 * MHz)
            ramp_limit_low = self.dds1.frequency_to_ftw(FREQ - 30 * MHz)
            ramp_rate = 0x004F004F
            ramp_step = 0xF0
            pulse_duration = 1 * s if not self.with_hold else 0.25 * s
        elif self.drg_destination == 0x1:  # Phase
            ramp_limit_high = 0xFFFFFFFF
            ramp_limit_low = 0
            ramp_rate = 0xC350C350
            ramp_step = 0xD1B71
            pulse_duration = 2 * s if not self.with_hold else 0.25 * s
        else:  # Amplitude
            ramp_limit_high = 0xFFFFFFFF
            ramp_limit_low = 0
            ramp_rate = 0xC350C350
            ramp_step = 0xD1B71
            pulse_duration = 2 * s if not self.with_hold else 0.4 * s

        self.dds1.write64(_AD9910_REG_RAMP_LIMIT, ramp_limit_high, ramp_limit_low)
        self.dds1.write32(_AD9910_REG_RAMP_RATE, ramp_rate)
        self.dds1.write64(_AD9910_REG_RAMP_STEP, ramp_step, ramp_step)

        self.dds1.set_cfr2(
            drg_enable=1,
            drg_destination=self.drg_destination,
            drg_nodwell_high=self.nodwell,
            drg_nodwell_low=self.nodwell,
        )
        self.dds1.io_update.pulse(1 * ms)

        # Enable waveform and set attenuation
        self.dds1.cfg_sw(True)
        self.dds1.set_att(ATT)
        if self.use_dds2:
            self.dds2.cfg_sw(True)
            self.dds2.set_att(ATT)

        if not self.nodwell:
            for _ in range(5):
                if self.with_hold:
                    self.dds1.cfg_drctl(True)
                    delay(pulse_duration)
                    self.dds1.cfg_drhold(True)
                    delay(pulse_duration)
                    self.dds1.cfg_drhold(False)
                    delay(pulse_duration)
                    self.dds1.cfg_drctl(False)
                    delay(pulse_duration)
                    self.dds1.cfg_drhold(True)
                    delay(pulse_duration)
                    self.dds1.cfg_drhold(False)
                    delay(pulse_duration)
                else:
                    self.dds1.cfg_drctl(True)
                    delay(pulse_duration)
                    self.dds1.cfg_drctl(False)
                    delay(pulse_duration)
        else:
            delay(10 * s)

        # Disable waveform
        self.dds1.cfg_sw(False)
        if self.use_dds2:
            self.dds2.cfg_sw(False)

        if not self.io_update_device:
            # Unset MASK_NU to un-trigger CFG.IO_UPDATE
            self.dds1.cfg_mask_nu(False)
            if self.use_dds2:
                self.dds2.cfg_mask_nu(False)

        # Unset ATT_EN
        self.dds1.cfg_att_en(False)
        if self.use_dds2:
            self.dds2.cfg_att_en(False)

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


class AD9910WaveformTest(ExperimentCase):
    def test_instantiate(self):
        self.execute(AD9910WaveformExp, "instantiate")

    @io_update_device(CPLD, True, False)
    def test_init(self, io_update_device):
        self.execute(AD9910WaveformExp, "init", io_update_device=io_update_device)

    @io_update_device(CPLD, True, False)
    def test_single_tone(self, io_update_device):
        self.execute(
            AD9910WaveformExp, "single_tone", io_update_device=io_update_device
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_8)
    def test_toggle_profiles(self, io_update_device):
        self.execute(
            AD9910WaveformExp,
            "toggle_profiles",
            io_update_device=io_update_device,
            multiple_profiles=False,
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_toggle_profiles(self, io_update_device):
        self.execute(
            AD9910WaveformExp,
            "toggle_profiles",
            io_update_device=io_update_device,
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_osk_manual(self, io_update_device):
        self.execute(AD9910WaveformExp, "osk", io_update_device=io_update_device)

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_osk_auto(self, io_update_device):
        self.execute(
            AD9910WaveformExp,
            "osk",
            io_update_device=io_update_device,
            osk_manual=False,
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal_frequency(self, io_update_device):
        self.execute(AD9910WaveformExp, "drg", io_update_device=io_update_device)

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal_phase(self, io_update_device):
        self.execute(
            AD9910WaveformExp,
            "drg",
            io_update_device=io_update_device,
            drg_destination=0x1,
            use_dds2=True,
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal_amplitude(self, io_update_device):
        self.execute(
            AD9910WaveformExp,
            "drg",
            io_update_device=io_update_device,
            drg_destination=0x2,
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal_with_hold_frequency(self, io_update_device):
        self.execute(
            AD9910WaveformExp, "drg", io_update_device=io_update_device, with_hold=True
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal_with_hold_phase(self, io_update_device):
        self.execute(
            AD9910WaveformExp,
            "drg",
            io_update_device=io_update_device,
            drg_destination=0x1,
            use_dds2=True,
            with_hold=True,
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_drg_normal_with_hold_amplitude(self, io_update_device):
        self.execute(
            AD9910WaveformExp,
            "drg",
            io_update_device=io_update_device,
            drg_destination=0x2,
            with_hold=True,
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_drg_nodwell_frequency(self, io_update_device):
        self.execute(
            AD9910WaveformExp, "drg", io_update_device=io_update_device, nodwell=1
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_drg_nodwell_phase(self, io_update_device):
        self.execute(
            AD9910WaveformExp,
            "drg",
            io_update_device=io_update_device,
            drg_destination=0x1,
            use_dds2=True,
            nodwell=1,
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_drg_nodwell_amplitude(self, io_update_device):
        self.execute(
            AD9910WaveformExp, "drg", io_update_device, drg_destination=0x2, nodwell=1
        )

    @io_update_device(CPLD, True, False, proto_rev=STA_PROTO_REV_9)
    def test_att_single_tone(self, io_update_device):
        self.execute(
            AD9910WaveformExp, "att_single_tone", io_update_device=io_update_device
        )
