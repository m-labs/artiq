from artiq.language.core import *
from artiq.language.db import *
from artiq.language.units import *
from artiq.coredevice import rtio


PHASE_MODE_DEFAULT = -1
PHASE_MODE_CONTINUOUS = 0
PHASE_MODE_ABSOLUTE = 1
PHASE_MODE_TRACKING = 2


class DDS(AutoDB):
    """Core device Direct Digital Synthesis (DDS) driver.

    Controls DDS devices managed directly by the core device's runtime. It also
    uses a RTIO channel (through :class:`artiq.coredevice.rtio.RTIOOut`) to
    control a RF switch that gates the output of the DDS device.

    :param dds_sysclk: DDS system frequency, used for computing the frequency
        tuning words.
    :param reg_channel: channel number of the DDS device to control.
    :param rtio_switch: RTIO channel number of the RF switch associated with
        the DDS device.

    """
    class DBKeys:
        core = Device()
        dds_sysclk = Parameter(1*GHz)
        reg_channel = Argument()
        rtio_switch = Argument()

    def build(self):
        self.previous_on = False
        self.previous_frequency = 0*MHz
        self.set_phase_mode(PHASE_MODE_CONTINUOUS)
        self.sw = rtio.RTIOOut(core=self.core, channel=self.rtio_switch)

    @portable
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.

        """
        return round(2**32*frequency/self.dds_sysclk)

    @portable
    def ftw_to_frequency(self, ftw):
        """Returns the frequency corresponding to the given frequency tuning
        word.

        """
        return ftw*self.dds_sysclk/2**32

    @kernel
    def set_phase_mode(self, phase_mode):
        """Sets the phase mode of the DDS channel. Supported phase modes are:

        * ``PHASE_MODE_CONTINUOUS``: the phase accumulator is unchanged when
          switching frequencies. The DDS phase is the sum of the phase
          accumulator and the phase offset. The only discrete jumps in the
          DDS output phase come from changes to the phase offset.

        * ``PHASE_MODE_ABSOLUTE``: the phase accumulator is reset when
          switching frequencies. Thus, the phase of the DDS at the time of
          the frequency change is equal to the phase offset.

        * ``PHASE_MODE_TRACKING``: when switching frequencies, the phase
          accumulator is set to the value it would have if the DDS had been
          running at the specified frequency since the start of the
          experiment.

        """
        self.phase_mode = phase_mode
        syscall("dds_phase_clear_en", self.reg_channel,
                self.phase_mode != PHASE_MODE_CONTINUOUS)

    @kernel
    def on(self, frequency, phase_mode=PHASE_MODE_DEFAULT, phase_offset=0):
        """Sets the DDS channel to the specified frequency and turns it on.

        If the DDS channel was already on, a real-time frequency and phase
        update is performed.

        :param frequency: frequency to generate.
        :param phase_mode: if specified, overrides the default phase mode set
            by ``set_phase_mode`` for this call.
        :param phase_offset: adds an offset, in turns, to the phase.

        """
        if phase_mode != PHASE_MODE_DEFAULT:
            old_phase_mode = self.phase_mode
            self.set_phase_mode(phase_mode)

        if self.previous_frequency != frequency:
            merge = self.sw.previous_timestamp == time_to_cycles(now())
            if not merge:
                self.sw.sync()
            # Channel is already on:
            # Precise timing of frequency change is required.
            # Channel is off:
            # Use soft timing on FUD to prevent conflicts when reprogramming
            # several channels that need to be turned on at the same time.
            rt_fud = merge or self.previous_on
            if self.phase_mode != PHASE_MODE_CONTINUOUS:
                sysclk_per_microcycle = int(self.dds_sysclk*
                                            self.core.ref_period)
            else:
                sysclk_per_microcycle = 0
            syscall("dds_program", time_to_cycles(now()), self.reg_channel,
               self.frequency_to_ftw(frequency), int(phase_offset*2**14),
               sysclk_per_microcycle,
               rt_fud, self.phase_mode == PHASE_MODE_TRACKING)
            self.previous_frequency = frequency
        self.sw.on()
        self.previous_on = True

        if phase_mode != PHASE_MODE_DEFAULT:
            self.set_phase_mode(old_phase_mode)

    @kernel
    def off(self):
        """Turns the DDS channel off.

        """
        self.sw.off()
        self.previous_on = False

    @kernel
    def pulse(self, frequency, duration,
              phase_mode=PHASE_MODE_DEFAULT, phase_offset=0):
        """Pulses the DDS channel for the specified duration at the specified
        frequency.

        See ``on`` for a description of the parameters.

        Equivalent to a ``on``, ``delay``, ``off`` sequence.

        """
        self.on(frequency, phase_mode, phase_offset)
        delay(duration)
        self.off()
