from artiq.coredevice.spline import Spline


class SAWG:
    """Smart arbitrary waveform generator channel.
    The channel is parametrized as: ::

        oscillators = exp(2j*pi*(frequency0*t + phase0))*(
            amplitude1*exp(2j*pi*(frequency1*t + phase1)) +
            amplitude2*exp(2j*pi*(frequency2*t + phase2)))

        output = (offset +
            i_enable*Re(oscillators) +
            q_enable*Im(buddy_oscillators))

    The nine spline interpolators are accessible as attributes:

    * :attr:`offset`, :attr:`amplitude1`, :attr:`amplitude2`: in units
      of full scale
    * :attr:`phase0`, :attr:`phase1`, :attr:`phase2`: in units of turns
    * :attr:`frequency0`, :attr:`frequency1`, :attr:`frequency2`: in units
      of Hz

    :param channel_base: RTIO channel number of the first channel (amplitude).
        Frequency and Phase are then assumed to be successive channels.
    :param parallelism: Number of output samples per coarse RTIO clock cycle.
    :param core_device: Name of the core device that this SAWG is on.
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
                             self.core, 2.)
        self.amplitude1 = Spline(width, time_width, channel_base + 2,
                                 self.core, 2*cordic_gain**2)
        self.frequency1 = Spline(3*width, time_width, channel_base + 3,
                                 self.core, 1/self.core.coarse_ref_period)
        self.phase1 = Spline(width, time_width, channel_base + 4,
                             self.core, 1.)
        self.amplitude2 = Spline(width, time_width, channel_base + 5,
                                 self.core, 2*cordic_gain**2)
        self.frequency2 = Spline(3*width, time_width, channel_base + 6,
                                 self.core, 1/self.core.coarse_ref_period)
        self.phase2 = Spline(width, time_width, channel_base + 7,
                             self.core, 1.)
        self.frequency0 = Spline(2*width, time_width, channel_base + 8,
                                 self.core,
                                 parallelism/self.core.coarse_ref_period)
        self.phase0 = Spline(width, time_width, channel_base + 9,
                             self.core, 1.)
