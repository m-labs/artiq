"""
Driver for the AD9914 DDS (with parallel bus) on RTIO.
"""


from artiq.language.core import *
from artiq.language.types import *
from artiq.language.units import *
from artiq.coredevice.rtio import rtio_output

from numpy import int32, int64


__all__ = [
    "AD9914",
    "PHASE_MODE_CONTINUOUS", "PHASE_MODE_ABSOLUTE", "PHASE_MODE_TRACKING"
]


_PHASE_MODE_DEFAULT   = -1
PHASE_MODE_CONTINUOUS = 0
PHASE_MODE_ABSOLUTE   = 1
PHASE_MODE_TRACKING   = 2

AD9914_REG_CFR1L = 0x01
AD9914_REG_CFR1H = 0x03
AD9914_REG_CFR2L = 0x05
AD9914_REG_CFR2H = 0x07
AD9914_REG_CFR3L = 0x09
AD9914_REG_CFR3H = 0x0b
AD9914_REG_CFR4L = 0x0d
AD9914_REG_CFR4H = 0x0f
AD9914_REG_DRGFL = 0x11
AD9914_REG_DRGFH = 0x13
AD9914_REG_DRGBL = 0x15
AD9914_REG_DRGBH = 0x17
AD9914_REG_DRGAL = 0x19
AD9914_REG_DRGAH = 0x1b
AD9914_REG_POW   = 0x31
AD9914_REG_ASF   = 0x33
AD9914_REG_USR0  = 0x6d
AD9914_FUD       = 0x80
AD9914_GPIO      = 0x81


class AD9914:
    """Driver for one AD9914 DDS channel.

    The time cursor is not modified by any function in this class.

    Output event replacement is not supported and issuing commands at the same
    time is an error.

    :param sysclk: DDS system frequency. The DDS system clock must be a
        phase-locked multiple of the RTIO clock.
    :param bus_channel: RTIO channel number of the DDS bus.
    :param channel: channel number (on the bus) of the DDS device to control.
    """

    kernel_invariants = {"core", "sysclk", "bus_channel", "channel",
        "rtio_period_mu", "sysclk_per_mu", "write_duration_mu",
        "dac_cal_duration_mu", "init_duration_mu", "init_sync_duration_mu",
        "set_duration_mu", "set_x_duration_mu", "exit_x_duration_mu"}

    def __init__(self, dmgr, sysclk, bus_channel, channel, core_device="core"):
        self.core        = dmgr.get(core_device)
        self.sysclk      = sysclk
        self.bus_channel = bus_channel
        self.channel     = channel
        self.phase_mode  = PHASE_MODE_CONTINUOUS

        self.rtio_period_mu        = int64(8)
        self.sysclk_per_mu         = int32(self.sysclk * self.core.ref_period)

        self.write_duration_mu     = 5 * self.rtio_period_mu
        self.dac_cal_duration_mu   = 147000 * self.rtio_period_mu
        self.init_duration_mu      = 13 * self.write_duration_mu + self.dac_cal_duration_mu
        self.init_sync_duration_mu = 21 * self.write_duration_mu + 2 * self.dac_cal_duration_mu
        self.set_duration_mu       = 7 * self.write_duration_mu
        self.set_x_duration_mu     = 7 * self.write_duration_mu
        self.exit_x_duration_mu    = 3 * self.write_duration_mu

    @kernel
    def write(self, addr, data):
        rtio_output((self.bus_channel << 8) | addr, data)
        delay_mu(self.write_duration_mu)

    @kernel
    def init(self):
        """Resets and initializes the DDS channel.

        This needs to be done for each DDS channel before it can be used, and
        it is recommended to use the startup kernel for this purpose.
        """
        delay_mu(-self.init_duration_mu)
        self.write(AD9914_GPIO,      (1 << self.channel) << 1);

        # Note another undocumented "feature" of the AD9914:
        # Programmable modulus breaks if the digital ramp enable bit is
        # not set at the same time.
        self.write(AD9914_REG_CFR1H, 0x0000) # Enable cosine output
        self.write(AD9914_REG_CFR2L, 0x8900) # Enable matched latency
        self.write(AD9914_REG_CFR2H, 0x0089) # Enable profile mode + programmable modulus + DRG
        self.write(AD9914_REG_DRGAL, 0)      # Programmable modulus A = 0
        self.write(AD9914_REG_DRGAH, 0)
        self.write(AD9914_REG_DRGBH, 0x8000) # Programmable modulus B == 2**31
        self.write(AD9914_REG_DRGBL, 0x0000)
        self.write(AD9914_REG_ASF,   0x0fff) # Set amplitude to maximum
        self.write(AD9914_REG_CFR4H, 0x0105) # Enable DAC calibration
        self.write(AD9914_FUD,       0)
        delay_mu(self.dac_cal_duration_mu)
        self.write(AD9914_REG_CFR4H, 0x0005) # Disable DAC calibration
        self.write(AD9914_FUD,       0)

    @kernel
    def init_sync(self, sync_delay):
        """Resets and initializes the DDS channel as well as configures
        the AD9914 DDS for synchronisation. The synchronisation procedure
        follows the steps outlined in the AN-1254 application note.

        This needs to be done for each DDS channel before it can be used, and
        it is recommended to use the startup kernel for this.

        This function cannot be used in a batch; the correct way of
        initializing multiple DDS channels is to call this function
        sequentially with a delay between the calls. 10ms provides a good
        timing margin.

        :param sync_delay: integer from 0 to 0x3f that sets the value of
            SYNC_OUT (bits 3-5) and SYNC_IN (bits 0-2) delay ADJ bits.
        """
        delay_mu(-self.init_sync_duration_mu)
        self.write(AD9914_GPIO,      (1 << self.channel) << 1)

        self.write(AD9914_REG_CFR4H, 0x0105) # Enable DAC calibration
        self.write(AD9914_FUD,       0)
        delay_mu(self.dac_cal_duration_mu)
        self.write(AD9914_REG_CFR4H, 0x0005) # Disable DAC calibration
        self.write(AD9914_FUD,       0)
        self.write(AD9914_REG_CFR2L, 0x8b00) # Enable matched latency and sync_out
        self.write(AD9914_FUD,       0)
        # Set cal with sync and set sync_out and sync_in delay
        self.write(AD9914_REG_USR0,  0x0840 | (sync_delay & 0x3f))
        self.write(AD9914_FUD,       0)
        self.write(AD9914_REG_CFR4H, 0x0105) # Enable DAC calibration
        self.write(AD9914_FUD,       0)
        delay_mu(self.dac_cal_duration_mu)
        self.write(AD9914_REG_CFR4H, 0x0005) # Disable DAC calibration
        self.write(AD9914_FUD,       0)
        self.write(AD9914_REG_CFR1H, 0x0000) # Enable cosine output
        self.write(AD9914_REG_CFR2H, 0x0089) # Enable profile mode + programmable modulus + DRG
        self.write(AD9914_REG_DRGAL, 0)      # Programmable modulus A = 0
        self.write(AD9914_REG_DRGAH, 0)
        self.write(AD9914_REG_DRGBH, 0x8000) # Programmable modulus B == 2**31
        self.write(AD9914_REG_DRGBL, 0x0000)
        self.write(AD9914_REG_ASF,   0x0fff) # Set amplitude to maximum
        self.write(AD9914_FUD,       0)

    @kernel
    def set_phase_mode(self, phase_mode):
        """Sets the phase mode of the DDS channel. Supported phase modes are:

        * :const:`PHASE_MODE_CONTINUOUS`: the phase accumulator is unchanged when
          switching frequencies. The DDS phase is the sum of the phase
          accumulator and the phase offset. The only discrete jumps in the
          DDS output phase come from changes to the phase offset.

        * :const:`PHASE_MODE_ABSOLUTE`: the phase accumulator is reset when
          switching frequencies. Thus, the phase of the DDS at the time of
          the frequency change is equal to the phase offset.

        * :const:`PHASE_MODE_TRACKING`: when switching frequencies, the phase
          accumulator is set to the value it would have if the DDS had been
          running at the specified frequency since the start of the
          experiment.

        .. warning:: This setting may become inconsistent when used as part of
            a DMA recording. When using DMA, it is recommended to specify the
            phase mode explicitly when calling :meth:`set` or :meth:`set_mu`.
        """
        self.phase_mode = phase_mode

    @kernel
    def set_mu(self, ftw, pow=0, phase_mode=_PHASE_MODE_DEFAULT,
               asf=0x0fff, ref_time_mu=-1):
        """Sets the DDS channel to the specified frequency and phase.

        This uses machine units (FTW and POW). The frequency tuning word width
        is 32, the phase offset word width is 16, and the amplitude scale factor
        width is 12.

        The "frequency update" pulse is sent to the DDS with a fixed latency
        with respect to the current position of the time cursor.

        :param ftw: frequency to generate.
        :param pow: adds an offset to the phase.
        :param phase_mode: if specified, overrides the default phase mode set
            by :meth:`set_phase_mode` for this call.
        :param ref_time_mu: reference time used to compute phase. Specifying this
            makes it easier to have a well-defined phase relationship between
            DDSes on the same bus that are updated at a similar time.
        :return: Resulting phase offset word after application of phase
            tracking offset. When using :const:`PHASE_MODE_CONTINUOUS` in
            subsequent calls, use this value as the "current" phase.
        """
        if phase_mode == _PHASE_MODE_DEFAULT:
            phase_mode = self.phase_mode
        if ref_time_mu < 0:
            ref_time_mu = now_mu()
        delay_mu(-self.set_duration_mu)

        self.write(AD9914_GPIO,      (1 << self.channel) << 1)

        self.write(AD9914_REG_DRGFL, ftw & 0xffff)
        self.write(AD9914_REG_DRGFH, (ftw >> 16) & 0xffff)

        # We need the RTIO fine timestamp clock to be phase-locked
        # to DDS SYSCLK, and divided by an integer self.sysclk_per_mu.
        if phase_mode == PHASE_MODE_CONTINUOUS:
            # Do not clear phase accumulator on FUD
            # Disable autoclear phase accumulator and enables OSK.
            self.write(AD9914_REG_CFR1L, 0x0108)
        else:
            # Clear phase accumulator on FUD
            # Enable autoclear phase accumulator and enables OSK.
            self.write(AD9914_REG_CFR1L, 0x2108)
            fud_time = now_mu() + 2 * self.write_duration_mu
            pow -= int32((ref_time_mu - fud_time) * self.sysclk_per_mu * ftw >> (32 - 16))
            if phase_mode == PHASE_MODE_TRACKING:
                pow += int32(ref_time_mu * self.sysclk_per_mu * ftw >> (32 - 16))

        self.write(AD9914_REG_POW,  pow)
        self.write(AD9914_REG_ASF,  asf)
        self.write(AD9914_FUD,      0)
        return pow

    @portable(flags={"fast-math"})
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.
        """
        return round(float(int64(2)**32*frequency/self.sysclk))

    @portable(flags={"fast-math"})
    def ftw_to_frequency(self, ftw):
        """Returns the frequency corresponding to the given frequency tuning
        word.
        """
        return ftw*self.sysclk/int64(2)**32

    @portable(flags={"fast-math"})
    def turns_to_pow(self, turns):
        """Returns the phase offset word corresponding to the given phase
        in turns."""
        return round(float(turns*2**16))

    @portable(flags={"fast-math"})
    def pow_to_turns(self, pow):
        """Returns the phase in turns corresponding to the given phase offset
        word."""
        return pow/2**16

    @portable(flags={"fast-math"})
    def amplitude_to_asf(self, amplitude):
        """Returns amplitude scale factor corresponding to given amplitude."""
        return round(float(amplitude*0x0fff))

    @portable(flags={"fast-math"})
    def asf_to_amplitude(self, asf):
        """Returns the amplitude corresponding to the given amplitude scale
           factor."""
        return asf/0x0fff

    @kernel
    def set(self, frequency, phase=0.0, phase_mode=_PHASE_MODE_DEFAULT,
            amplitude=1.0):
        """Like :meth:`set_mu`, but uses Hz and turns."""
        return self.pow_to_turns(
            self.set_mu(self.frequency_to_ftw(frequency),
                    self.turns_to_pow(phase), phase_mode,
                    self.amplitude_to_asf(amplitude)))

    # Extended-resolution functions
    @kernel
    def set_x_mu(self, xftw, amplitude=0x0fff):
        """Set the DDS frequency and amplitude with an extended-resolution
        (63-bit) frequency tuning word.

        Phase control is not implemented in this mode; the phase offset
        can assume any value.

        After this function has been called, exit extended-resolution mode
        before calling functions that use standard-resolution mode.
        """
        delay_mu(-self.set_x_duration_mu)

        self.write(AD9914_GPIO,      (1 << self.channel) << 1)

        self.write(AD9914_REG_DRGAL, xftw & 0xffff)
        self.write(AD9914_REG_DRGAH, (xftw >> 16) & 0x7fff)
        self.write(AD9914_REG_DRGFL, (xftw >> 31) & 0xffff)
        self.write(AD9914_REG_DRGFH, (xftw >> 47) & 0xffff)
        self.write(AD9914_REG_ASF,   amplitude)

        self.write(AD9914_FUD,       0)

    @kernel
    def exit_x(self):
        """Exits extended-resolution mode."""
        delay_mu(-self.exit_x_duration_mu)
        self.write(AD9914_GPIO,      (1 << self.channel) << 1)
        self.write(AD9914_REG_DRGAL, 0)
        self.write(AD9914_REG_DRGAH, 0)

    @portable(flags={"fast-math"})
    def frequency_to_xftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency (extended resolution mode).
        """
        return int64(round(2.0*float(int64(2)**62)*frequency/self.sysclk))

    @portable(flags={"fast-math"})
    def xftw_to_frequency(self, xftw):
        """Returns the frequency corresponding to the given frequency tuning
        word (extended resolution mode).
        """
        return xftw*self.sysclk/(2.0*float(int64(2)**62))

    @kernel
    def set_x(self, frequency, amplitude=1.0):
        """Like :meth:`set_x_mu`, but uses Hz and turns.

        Note that the precision of ``float`` is less than the precision
        of the extended frequency tuning word.
        """
        self.set_x_mu(self.frequency_to_xftw(frequency),
                      self.amplitude_to_asf(amplitude))
