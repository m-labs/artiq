from numpy import int32, int64

from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import us

PHASER_GW_VARIANT_MTDDS = 1

[
    HW_VARIANT,
    GW_VARIANT,
    SAMPLE_PER_CYCLE,
    AVAILABLE_TONES,
    DAC_CTRL_ADDR,
    DAC_STATUS_ADDR,
    DAC_SOURCE_SEL_ADDR,
    DAC_TEST_WORD_0_I_ADDR,
    DAC_TEST_WORD_0_Q_ADDR,
    DAC_TEST_WORD_1_I_ADDR,
    DAC_TEST_WORD_1_Q_ADDR,
    ATT_RESET_N,
    TRF_PS,
    TRF_LOCK_DETECT,
] = range(14)


class _DummyIQUpconverter:
    def __init__(self):
        self.use_external_lo = False

    @portable
    def init(self):
        pass


class PhaserMTDDS:
    """Phaser FPGA and DAC DAC34H84 configuration interface.

    :param sysclk: Sysclk frequency
    :param dac_device: DAC device name.
    :param core_device: Core device name (default: "core").

    Attributes:

    * :attr:`dac`: A :class:`DAC34H84<artiq.coredevice.dac34h84.DAC34H84>`.

    """

    kernel_invariants = {
        "core",
        "channel",
        "dac",
        "samples_per_cycle",
        "target_write",
        "target_read",
    }

    def __init__(
        self,
        dmgr,
        channel,
        sysclk,
        dac_device,
        core_device="core",
    ):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.dac = dmgr.get(dac_device)

        self.samples_per_cycle = int(self.dac.input_sample_rate / sysclk)

        self.target_write = self.channel << 8
        self.target_read = self.channel << 8 | 1 << 4

    @staticmethod
    def get_rtio_channels(channel_base, **kwargs):
        return [(channel_base, "base")]

    @kernel
    def init(self):
        """Initialize the Phaser.

        Verify the gateware variant, initialize and test the DAC.
        """
        if self.read(GW_VARIANT) != PHASER_GW_VARIANT_MTDDS:
            raise ValueError("PhaserMTDDS gateware variant mismatch")
        delay(40.0 * us)
        if self.read(SAMPLE_PER_CYCLE) != self.samples_per_cycle:
            raise ValueError("PhaserMTDDS samples per cycle (DDS bandwidth) mismatch")
        delay(40.0 * us)

        # Toggle reset and keep tx off
        self.set_dac_ctrl(txena=False, reset=True, sleep=False)
        self.set_dac_ctrl(txena=False, reset=False, sleep=False)
        delay(10.0 * us) # slack

        self.dac.init()

        test_patterns = [
            [
                0x7A7A,
                0xB6B6,
                0xEAEA,
                0x4545,
            ],  # datasheet test word pattern a - SLAS751D Table 37-40
            [
                0x1A1A,
                0x1616,
                0xAAAA,
                0xC6C6,
            ],  # datasheet test word pattern b - SLAS751D Table 41-44
        ]
        for p in test_patterns:
            self.test_dac(p)

        # enable DAC tx
        self.set_dac_ctrl(txena=True, reset=False, sleep=False)

    @kernel
    def write(self, address, data):
        rtio_output(self.target_write | address, data)

    @kernel
    def read(self, address):
        rtio_output(self.target_read | address, 0)
        return rtio_input_data(self.channel)

    @kernel
    def reset_attenuator(self, channel):
        reg = self.read(ATT_RESET_N)
        delay(40.0 * us)
        self.write(ATT_RESET_N, reg & ~(1 << channel))
        delay_mu(int64(self.core.ref_multiplier))
        self.write(ATT_RESET_N, reg | 1 << channel)
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def is_upconverter_variant(self) -> TBool:
        is_upconverter = self.read(HW_VARIANT) == 0
        return is_upconverter

    @kernel
    def upconverter_pll_locked(self, channel) -> TBool:
        """Return True when the upconverter PLL locks and False when the PLL unlocks

        This method consumes all slack.

        :param channel: Phaser channel number (0 or 1)
        """
        locked = (self.read(TRF_LOCK_DETECT) >> channel) & 0b1 == 0b1
        return locked

    @kernel
    def get_available_tones(self) -> TInt32:
        tones = self.read(AVAILABLE_TONES)
        return tones

    @kernel
    def select_dac_source(self, channel, source):
        """Select the input source of the DAC34H84

        :param channel: Phaser channel number (0 or 1)
        :param source: 2-bit source select register (set to 0 for test word, 1 for DDSs)
        """
        reg = self.read(DAC_SOURCE_SEL_ADDR)
        delay(40.0 * us)
        self.write(
            DAC_SOURCE_SEL_ADDR,
            (reg & ~(0b11 << (2 * channel))) | (source & 0b11) << (2 * channel),
        )
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def set_dac_ctrl(self, txena, reset, sleep):
        """Set DAC34H84 control register.

        :param txena: Enable DAC34H84 TX when set to True
        :param reset: Reset DAC34H84 when set to True
        :param sleep: Power down DAC34H84 when set to True
        """
        reg = 0
        if txena:
            reg |= 1
        if not reset:
            # bit1 = resetb
            reg |= 1 << 1
        if sleep:
            reg |= 1 << 2
        self.write(DAC_CTRL_ADDR, reg)
        delay_mu(int64(self.core.ref_multiplier))

    @kernel
    def test_dac(self, pattern):
        """Start DAC34H84 iotest via internal data pattern checker

        :param pattern: a list of 16-bit test words
        """
        if len(pattern) != 4:
            raise ValueError("pattern length mismatch")

        test_word_addr = [
            DAC_TEST_WORD_0_I_ADDR,
            DAC_TEST_WORD_0_Q_ADDR,
            DAC_TEST_WORD_1_I_ADDR,
            DAC_TEST_WORD_1_Q_ADDR,
        ]

        for i in range(len(pattern)):
            # repeat the pattern twice
            self.dac.write(0x25 + i, pattern[i])
            self.dac.write(0x29 + i, pattern[i])
            self.write(test_word_addr[i], pattern[i])
            delay_mu(int64(self.core.ref_multiplier))

        # start writing test words to DAC
        self.select_dac_source(0, 0)
        self.select_dac_source(1, 0)

        reg_0x01 = self.dac.read(0x01)
        delay(40.0 * us)
        # enable iotest & clear iotest_result
        self.dac.write(0x01, reg_0x01 | 0x8000)
        self.dac.write(0x04, 0x0000)

        # let it run for a while
        delay(100.0 * us)

        iotest_error = self.dac.read(0x04)
        delay(40.0 * us)
        if iotest_error != 0:
            raise ValueError("DAC iotest failure")

        # disable iotest
        self.dac.write(0x01, reg_0x01)

        # stop writing test words to DAC
        self.select_dac_source(0, 1)
        self.select_dac_source(1, 1)


class PhaserMTDDSChannel:
    """Phaser channel with IQ multitone DDS.

    This class supports a channel with multiple IQ DDSs and exposes the channel devices:

    * baseband hardware variant: multitone DDSs and digital step attenuator
    * upconverter hardware variant: multitone DDSs, digital step attenuator and upconverter

    .. note:: Due to hardware limitation, it's not possible to use external LO in channel 1 upconverter and use internal VCO in channel 0 upconverter.
              As the upconverter external LO input in channel 1 is directly connected to the upconverter LO output in channel 0.

    :param tones: Total number of IQ DDSs
    :param fpga_device: Phaser FPGA device name.
    :param dac_device: DAC device name.
    :param att_device: Attenuator device name.
    :param dds_device_prefix: Phaser IQ DDS device name prefix.
    :param iquc_device: Upconverter device name (defualt: None)
    :param core_device: Core device name (default: "core").

    Attributes:

    * :attr:`attenuator`: A :class:`HMC542B<artiq.coredevice.hmc542b.HMC542B>`.
    * :attr:`upconverter`: A :class:`TRF372017<artiq.coredevice.trf372017.TRF372017>` if ``iquc_device`` is provided.
    * :attr:`ddss`: List of :class:`PhaserDDS`.

    """

    kernel_invariants = {
        "core",
        "channel_index",
        "tones",
        "fpga",
        "dac",
        "attenuator",
        "has_upconverter",
        "upconverter",
        "ddss",
    }

    def __init__(
        self,
        dmgr,
        channel_index,
        tones,
        fpga_device,
        dac_device,
        att_device,
        dds_device_prefix,
        iquc_device=None,
        core_device="core",
    ):
        self.core = dmgr.get(core_device)
        self.channel_index = channel_index
        self.tones = tones

        self.fpga = dmgr.get(fpga_device)
        self.dac = dmgr.get(dac_device)
        self.attenuator = dmgr.get(att_device)

        if iquc_device is None:
            self.upconverter = _DummyIQUpconverter()
            self.has_upconverter = False
        else:
            self.upconverter = dmgr.get(iquc_device)
            self.has_upconverter = True
        self.ddss = [dmgr.get(dds_device_prefix + str(i)) for i in range(tones)]

    @kernel
    def init(self):
        """Initialize the Phaser channel.

        Verify the number of tones and hardware variant, reset attenuators and initialize upconverter if available.
        """
        if self.fpga.get_available_tones() != self.tones:
            raise ValueError("PhaserMTDDS number of available tones mismatch")
        delay(40.0 * us)
        if self.has_upconverter != self.fpga.is_upconverter_variant():
            raise ValueError("PhaserMTDDS hardware variant mismatch")
        delay(40.0 * us)

        self.fpga.reset_attenuator(self.channel_index)
        delay(10.0 * us) # slack

        if self.has_upconverter:
            self.upconverter.init()

            # SLWS224E datasheet didn't mention any PLL lock time, 500 us should be enough
            delay(500 * us)

            # External LO doesn't use PLL, no need to check lock status
            if not (self.upconverter.use_external_lo or self.upconverter_pll_locked()):
                raise ValueError("TRF372017 PLL fails to lock")
            delay(40.0 * us)

    @kernel
    def upconverter_pll_locked(self) -> TBool:
        """Returns whether the upconverter PLL is locked

        This method consumes all slack.

        See also :meth:`PhaserMTDDS.upconverter_pll_locked`

        """
        if self.upconverter.use_external_lo: 
            raise ValueError("External LO is used and PLL is bypassed")
        return self.fpga.upconverter_pll_locked(self.channel_index)

    @kernel
    def stage_dac_nco_mixer_frequency_mu(self, ftw):
        """Stage the DAC NCO mixer frequency in machine units.

        Before using DAC NCO mixer, the mixer must be enabled via :meth:`DAC34H84.enable_mixer<artiq.coredevice.dac34h84.DAC34H84.enable_mixer>`.
        The settings is only applied after triggering DAC synchronisation via :meth:`DAC34H84.sync<artiq.coredevice.dac34h84.DAC34H84.sync>`.

        See also :meth:`DAC34H84.stage_nco_mixer_frequency_mu<artiq.coredevice.dac34h84.DAC34H84.stage_nco_mixer_frequency_mu>`

        :param ftw: 32-bit NCO frequency tuning word
        """
        self.dac.stage_nco_mixer_frequency_mu(self.channel_index, ftw)

    @kernel
    def stage_dac_nco_mixer_phase_offset_mu(self, pow):
        """Stage the DAC NCO mixer phase offset in machine units.

        Before using DAC NCO mixer, the mixer must be enabled via :meth:`DAC34H84.enable_mixer<artiq.coredevice.dac34h84.DAC34H84.enable_mixer>`.
        The settings is only applied after triggering DAC synchronisation via :meth:`DAC34H84.sync<artiq.coredevice.dac34h84.DAC34H84.sync>`.

        See also :meth:`DAC34H84.stage_nco_mixer_phase_offset_mu<artiq.coredevice.dac34h84.DAC34H84.stage_nco_mixer_phase_offset_mu>`

        :param ftw: 16-bit NCO phase offset word
        """
        self.dac.stage_nco_mixer_phase_offset_mu(self.channel_index, pow)

    @kernel
    def stage_dac_nco_mixer_frequency(self, frequency):
        """Stage the DAC NCO mixer frequency in SI units.

        Before using DAC NCO mixer, the mixer must be enabled via :meth:`DAC34H84.enable_mixer<artiq.coredevice.dac34h84.DAC34H84.enable_mixer>`.
        The settings is only applied after triggering DAC synchronisation via :meth:`DAC34H84.sync<artiq.coredevice.dac34h84.DAC34H84.sync>`.

        See also :meth:`DAC34H84.stage_nco_mixer_frequency<artiq.coredevice.dac34h84.DAC34H84.stage_nco_mixer_frequency>`

        :param frequency: NCO frequency in Hz (-500 MHz to +500 MHz)
        """
        self.dac.stage_nco_mixer_frequency(self.channel_index, frequency)

    @kernel
    def stage_dac_nco_mixer_phase_offset(self, phase):
        """Stage the DAC NCO mixer phase offset in SI units.

        Before using DAC NCO mixer, the mixer must be enabled via :meth:`DAC34H84.enable_mixer<artiq.coredevice.dac34h84.DAC34H84.enable_mixer>`.
        The settings is only applied after triggering DAC synchronisation via :meth:`DAC34H84.sync<artiq.coredevice.dac34h84.DAC34H84.sync>`.

        See also :meth:`DAC34H84.stage_nco_mixer_phase_offset<artiq.coredevice.dac34h84.DAC34H84.stage_nco_mixer_phase_offset>`

        :param phase: NCO phase offset in turns (0.0 to 1.0)
        """
        self.dac.stage_nco_mixer_phase_offset(self.channel_index, phase)


class PhaserDDS:
    """Phaser IQ DDS driver

    :param bandwidth: DDS bandwidth
    :param core_device: Core device name (default: "core").
    """

    kernel_invariants = {"core", "channel"}

    def __init__(self, dmgr, channel, bandwidth, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)

        self.bandwidth = bandwidth
        self.target_ftw = (self.channel << 8) | 0
        self.target_pow = (self.channel << 8) | 1
        self.target_asf = (self.channel << 8) | 2
        self.target_clear = (self.channel << 8) | 3

    @staticmethod
    def get_rtio_channels(channel_base, **kwargs):
        return [(channel_base, "channel")]

    @kernel
    def set_frequency_mu(self, ftw):
        """Set the DDS frequency in machine units.

        :param ftw: 32-bit DDS frequency tuning word
        """
        rtio_output(self.target_ftw, ftw)

    @kernel
    def set_phase_offset_mu(self, pow):
        """Set the DDS phase offset in machine units.

        :param ftw: 16-bit DDS phase offset word
        """
        rtio_output(self.target_pow, pow)

    @kernel
    def set_amplitude_mu(self, asf):
        """Set the DDS amplitude in machine units.

        :param ftw: 16-bit DDS amplitude scale factor
        """
        rtio_output(self.target_asf, asf)

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency) -> TInt32:
        """Return the 32-bit frequency tuning word corresponding to the given frequency in Hz."""
        return int32(round((int64(1) << 32) * (frequency / self.bandwidth)))

    @portable(flags={"fast-math"})
    def turns_to_pow(self, turns) -> TInt32:
        """Return the 16-bit phase offset word corresponding to the given phase in turns."""
        return int32(round(turns * (1 << 16)))

    @portable(flags={"fast-math"})
    def amplitude_to_asf(self, amplitude) -> TInt32:
        """Return the 16-bit amplitude scale factor corresponding to the given fractional amplitude."""
        return int32(round(amplitude * ((1 << 15) - 1)))

    @kernel
    def set_frequency(self, frequency):
        """Set the DDS frequency in SI units.

        Due to different DAC interpolation ratio between DDS bandwidth, the resulting frequency responses are different between bandwidths:

        * 250 MHz DDS bandwidth: passband from -100 MHz to +100 MHz, wrapping around at ±125 MHz
        * 500 MHz DDS bandwidth: passband from -200 MHz to +200 MHz, wrapping around at ±250 MHz

        :param frequency: DDS frequency in Hz
        """
        self.set_frequency_mu(self.frequency_to_ftw(frequency))

    @kernel
    def set_phase_offset(self, phase):
        """Set the DDS phase offset in SI units.

        :param phase: DDS phase offset in turns (0.0 to 1.0)
        """
        self.set_phase_offset_mu(self.turns_to_pow(phase))

    @kernel
    def set_amplitude(self, amplitude):
        """Set the DDS amplitude in SI units.

        :param amplitude: DDS amplitude (-1.0 to 1.0)
        """
        self.set_amplitude_mu(self.amplitude_to_asf(amplitude))

    @kernel
    def enable_phase_accumulator(self, enable):
        """Enable/disable the DDS phase accmulator.

        When the phase accmulator is disabled, the phase value is set to zero.
        Otherwise, the frequency tuning word is added to the accmulator at each clock cycle.

        :param enable: Enable the DDS phase accmulator if True
        """
        rtio_output(self.target_clear, 0 if enable else 1)
