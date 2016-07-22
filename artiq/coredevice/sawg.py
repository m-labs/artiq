from artiq.language.core import kernel, now_mu
from artiq.coredevice.rtio import rtio_output
from artiq.language.types import TInt32, TFloat


class SAWG:
    """Smart arbitrary waveform generator channel.

    :param channel_base: RTIO channel number of the first channel (amplitude).
        Frequency and Phase are then assumed to be successive channels.
    """
    kernel_invariants = {"amplitude_scale", "frequency_scale", "phase_scale",
                         "channel_base"}

    def __init__(self, dmgr, channel_base, parallelism=4, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel_base = channel_base
        cordic_gain = 1.646760258057163  # Cordic(width=16, guard=None).gain
        a_width = 16
        f_width = 32
        p_width = 16
        self.amplitude_scale = (1 << a_width) / 2 / cordic_gain
        self.phase_scale = 1 << p_width
        self.frequency_scale = ((1 << f_width) * self.core.coarse_ref_period /
                                parallelism)

    @kernel
    def set_amplitude_mu(self, amplitude: TInt32):
        """Set DDS amplitude (machine units).

        :param amplitude: DDS amplitude in machine units.
        """
        rtio_output(now_mu(), self.channel_base, 0, amplitude)

    @kernel
    def set_amplitude(self, amplitude: TFloat):
        """Set DDS amplitude.

        :param amplitude: DDS amplitude relative to full-scale.
        """
        self.set_amplitude_mu(int(amplitude*self.amplitude_scale))

    @kernel
    def set_frequency_mu(self, frequency: TInt32):
        """Set DDS frequency (machine units).

        :param frequency: DDS frequency in machine units.
        """
        rtio_output(now_mu(), self.channel_base + 1, 0, frequency)

    @kernel
    def set_frequency(self, frequency: TFloat):
        """Set DDS frequency.

        :param frequency: DDS frequency in Hz.
        """
        self.set_frequency_mu(int(frequency*self.frequency_scale))

    @kernel
    def set_phase_mu(self, phase: TInt32):
        """Set DDS phase (machine units).

        :param phase: DDS phase in machine units.
        """
        rtio_output(now_mu(), self.channel_base + 2, 0, phase)

    @kernel
    def set_phase(self, phase: TFloat):
        """Set DDS phase.

        :param phase: DDS phase relative in turns.
        """
        self.set_phase_mu(int(phase*self.phase_scale))
