from numpy import int32, int64
from artiq.language.core import kernel, now_mu, portable
from artiq.coredevice.rtio import rtio_output, rtio_output_list
from artiq.language.types import TInt32, TInt64, TFloat, TList


class Spline:
    kernel_invariants = {"channel", "core", "scale", "width",
                         "time_width", "time_scale"}

    def __init__(self, width, time_width, channel, core_device, scale=1.):
        self.core = core_device
        self.channel = channel
        self.width = width
        self.scale = (1 << width) / scale
        self.time_width = time_width
        self.time_scale = (1 << time_width) / core_device.coarse_ref_period

    @portable(flags=["fast-math"])
    def to_mu(self, value: TFloat) -> TInt32:
        return int(round(value*self.scale))

    @portable(flags=["fast-math"])
    def from_mu(self, value: TInt32) -> TFloat:
        return value/self.scale

    @portable(flags=["fast-math"])
    def to_mu64(self, value: TFloat) -> TList(TInt32):
        v = int64(round(value*self.scale))
        return [int32(v), int32(v >> 32)]

    @kernel
    def set_mu(self, value: TInt32):
        """Set spline value (machine units).

        :param value: Spline value in integer machine units.
        """
        rtio_output(now_mu(), self.channel, 0, value)

    @kernel
    def set(self, value: TFloat):
        """Set spline value.

        :param value: Spline value relative to full-scale.
        """
        rtio_output(now_mu(), self.channel, 0, self.to_mu(value))

    @kernel
    def set64(self, value: TFloat):
        """Set spline value.

        :param value: Spline value relative to full-scale.
        """
        rtio_output_list(now_mu(), self.channel, 0, self.to_mu64(value))

    @kernel
    def set_list_mu(self, value: TList(TInt32)):
        """Set spline raw values.

        :param value: Spline packed raw values.
        """
        rtio_output_list(now_mu(), self.channel, 0, value)

    @portable(flags=["fast-math"])
    def coeff_to_mu(self, value: TList(TFloat)) -> TList(TInt32):
        l = len(value)
        w = l*self.width + (l - 1)*l//2*self.time_width
        v = [0] * ((w + 31)//32)
        j = 0
        for i, vi in enumerate(value):
            w = self.width + i*self.time_width
            vi = int64(round(vi*(self.scale*self.time_scale**i)))
            for k in range(0, w, 16):
                wi = (vi >> k) & 0xffff
                v[j//2] += wi << (16 * ((j + 1)//2 - j//2))
                j += 1
        return v

    @kernel
    def set_list(self, value: TList(TFloat)):
        """Set spline coefficients.

        :param value: List of floating point spline knot coefficients,
            lowest order (constant) coefficient first.
        """
        self.set_list_mu(self.coeff_to_mu(value))


class SAWG:
    """Smart arbitrary waveform generator channel.
    The channel is parametrized as: ::

        oscillators = exp(2j*pi*(frequency0*t + phase0))*(
            amplitude1*exp(2j*pi*(frequency1*t + phase1)) +
            amplitude2*exp(2j*pi*(frequency2*t + phase2))

        output = (offset +
            i_enable*Re(oscillators) +
            q_enable*Im(buddy_oscillators))

    Where:
        * offset, amplitude1, amplitude1: in units of full scale
        * phase0, phase1, phase2: in units of turns
        * frequency0, frequency1, frequency2: in units of Hz

    :param channel_base: RTIO channel number of the first channel (amplitude).
        Frequency and Phase are then assumed to be successive channels.
    """
    kernel_invariants = {"channel_base", "core",
                         "amplitude1", "frequency1", "phase1",
                         "amplitude2", "frequency2", "phase2",
                         "frequency0", "phase0", "offset"}

    def __init__(self, dmgr, channel_base, parallelism, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel_base = channel_base
        width = 16
        time_width = 16
        cordic_gain = 1.646760258057163  # Cordic(width=16, guard=None).gain
        # cfg: channel_base
        self.offset = Spline(width, time_width, channel_base + 1,
                             self.core, 2)
        self.amplitude1 = Spline(width, time_width, channel_base + 2,
                                 self.core, 2*cordic_gain**2)
        self.frequency1 = Spline(3*width, time_width, channel_base + 3,
                                 self.core, self.core.coarse_ref_period)
        self.phase1 = Spline(width, time_width, channel_base + 4,
                             self.core, 1.)
        self.amplitude2 = Spline(width, time_width, channel_base + 5,
                                 self.core, 2*cordic_gain**2)
        self.frequency2 = Spline(3*width, time_width, channel_base + 6,
                                 self.core, self.core.coarse_ref_period)
        self.phase2 = Spline(width, time_width, channel_base + 7,
                             self.core, 1.)
        self.frequency0 = Spline(2*width, time_width, channel_base + 8,
                                 self.core,
                                 parallelism/self.core.coarse_ref_period)
        self.phase0 = Spline(width, time_width, channel_base + 9,
                             self.core, 1.)
