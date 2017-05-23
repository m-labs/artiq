from artiq.language.types import TInt32
from artiq.language.core import kernel, now_mu
from artiq.coredevice.spline import Spline
from artiq.coredevice.rtio import rtio_output


# sawg.Config addresses
_SAWG_DIV = 0
_SAWG_CLR = 1
_SAWG_IQ_EN = 2
# _SAWF_PAD = 3  # reserved
_SAWG_DUC_I_MIN = 4
_SAWG_DUC_I_MAX = 5
_SAWG_DUC_Q_MIN = 6
_SAWG_DUC_Q_MAX = 7
_SAWG_OUT_MIN = 8
_SAWG_OUT_MAX = 9


class Config:
    """SAWG configuration.

    Exposes the configurable quantities of a single SAWG channel.

    :param channel: RTIO channel number of the channel.
    :param core: Core device.
    """
    kernel_invariants = {"channel", "core"}

    def __init__(self, channel, core):
        self.channel = channel
        self.core = core

    @kernel
    def set_div(self, div: TInt32, n: TInt32=0):
        """Set the spline evolution divider and current counter value.

        The divider and the spline evolution are synchronized across all
        spline channels within a SAWG channel. The phase accumulator always
        evolves at full speed.

        :param div: Spline evolution divider, such that
            ``t_sawg_spline/t_rtio_coarse = div + 1``. Default: ``0``.
        :param n: Current value of the counter. Default: ``0``.
        """
        rtio_output(now_mu(), self.channel, _SAWG_DIV, div | (n << 16))

    @kernel
    def set_clr(self, clr0: TInt32, clr1: TInt32, clr2: TInt32):
        """Set the phase clear mode for the three phase accumulators.

        When the ``clr`` bit for a given phase accumulator is
        set, that phase accumulator will be cleared with every phase RTIO
        command and the output phase will be exactly the phase RTIO value
        ("absolute phase update mode").

        In turn, when the bit is cleared, the phase RTIO channels only
        provide a phase offset to the current value of the phase
        accumulator ("relative phase update mode").

        :param clr0: Auto-clear phase accumulator of the ``phase0``/
          ``frequency0`` DUC. Default: ``True``
        :param clr1: Auto-clear phase accumulator of the ``phase1``/
          ``frequency1`` DDS. Default: ``True``
        :param clr2: Auto-clear phase accumulator of the ``phase2``/
          ``frequency2`` DDS. Default: ``True``
        """
        rtio_output(now_mu(), self.channel, _SAWG_CLR, clr1 |
                (clr2 << 1) | (clr0 << 2))

    @kernel
    def set_iq_en(self, i_enable: TInt32, q_enable: TInt32):
        """Enable I/Q data on this DAC channel.

        Every pair of SAWG channels forms a buddy pair.
        The ``iq_en`` configuration controls which DDS data is emitted to the
        DACs.

        Refer to the documentation of :class:`SAWG` for a mathematical
        description of ``i_enable`` and ``q_enable``.

        :param i_enable: Controls adding the in-phase
              DUC-DDS data of *this* SAWG channel to *this* DAC channel.
              Default: ``1``.
        :param q_enable: controls adding the quadrature
              DUC-DDS data of this SAWG's *buddy* channel to *this* DAC
              channel. Default: ``0``.
        """
        rtio_output(now_mu(), self.channel, _SAWG_IQ_EN, i_enable |
                (q_enable << 1))

    @kernel
    def set_duc_i_max(self, limit: TInt32):
        """Set the digital up-converter (DUC) I data summing junction upper
        limit.

        Each of the three summing junctions has a saturating adder with
        configurable upper and lower limits. The three summing junctions are:

            * At the in-phase input to the ``phase0``/``frequency0`` fast DUC,
              where the in-phase outputs of the two slow DDS (1 and 2) are
              added together.
            * At the quadrature input to the ``phase0``/``frequency0``
              fast DUC, where the quadrature outputs of the two slow DDS
              (1 and 2) are added together.
            * Before the DAC, where the following three data streams
              are added together:

                * the output of the ``offset`` spline,
                * (optionally, depending on ``i_enable``) the in-phase output
                  of the ``phase0``/``frequency0`` fast DUC, and
                * (optionally, depending on ``q_enable``) the quadrature
                  output of the ``phase0``/``frequency0`` fast DUC of the
                  buddy channel.

        Refer to the documentation of :class:`SAWG` for a mathematical
        description of the summing junctions.

        The default limits are the full range of signed 16 bit data.

        .. seealso::
            * :meth:`set_duc_i_max`: Upper limit of the in-phase input to
              the DUC.
            * :meth:`set_duc_i_min`: Lower limit of the in-phase input to
              the DUC.
            * :meth:`set_duc_q_max`: Upper limit of the quadrature input to
              the DUC.
            * :meth:`set_duc_q_min`: Lower limit of the quadrature input to
              the DUC.
            * :meth:`set_out_max`: Upper limit of the DAC output.
            * :meth:`set_out_min`: Lower limit of the DAC output.
        """
        rtio_output(now_mu(), self.channel, _SAWG_DUC_I_MAX, limit)

    @kernel
    def set_duc_i_min(self, limit: TInt32):
        """.. seealso:: :meth:`set_duc_i_max`"""
        rtio_output(now_mu(), self.channel, _SAWG_DUC_I_MIN, limit)

    @kernel
    def set_duc_q_max(self, limit: TInt32):
        """.. seealso:: :meth:`set_duc_i_max`"""
        rtio_output(now_mu(), self.channel, _SAWG_DUC_Q_MAX, limit)

    @kernel
    def set_duc_q_min(self, limit: TInt32):
        """.. seealso:: :meth:`set_duc_i_max`"""
        rtio_output(now_mu(), self.channel, _SAWG_DUC_Q_MIN, limit)

    @kernel
    def set_out_max(self, limit: TInt32):
        """.. seealso:: :meth:`set_duc_i_max`"""
        rtio_output(now_mu(), self.channel, _SAWG_OUT_MAX, limit)

    @kernel
    def set_out_min(self, limit: TInt32):
        """.. seealso:: :meth:`set_duc_i_max`"""
        rtio_output(now_mu(), self.channel, _SAWG_OUT_MIN, limit)


class SAWG:
    """Smart arbitrary waveform generator channel.
    The channel is parametrized as: ::

        oscillators = exp(2j*pi*(frequency0*t + phase0))*(
            amplitude1*exp(2j*pi*(frequency1*t + phase1)) +
            amplitude2*exp(2j*pi*(frequency2*t + phase2)))

        output = (offset +
            i_enable*Re(oscillators) +
            q_enable*Im(buddy_oscillators))

    This parametrization can be viewed as two complex (quadrature) oscillators
    (``frequency1``/``phase1`` and ``frequency2``/``phase2``) followed by
    a complex digital up-converter (DUC, ``frequency0``/``phase0``) on top of a
    (real/in-phase) ``offset``. The ``i_enable``/``q_enable`` switches
    enable emission of quadrature signals for later analog quadrature mixing
    distinguishing upper and lower sidebands and thus doubling the bandwidth.
    They can also be used to emit four-tone signals.

    The configuration channel and the nine
    :class:`artiq.coredevice.spline.Spline` interpolators are accessible as
    attributes:

    * :attr:`config`: :class:`Config`
    * :attr:`offset`, :attr:`amplitude1`, :attr:`amplitude2`: in units
      of full scale
    * :attr:`phase0`, :attr:`phase1`, :attr:`phase2`: in units of turns
    * :attr:`frequency0`, :attr:`frequency1`, :attr:`frequency2`: in units
      of Hz

    :param channel_base: RTIO channel number of the first channel (amplitude).
        The configuration channel and frequency/phase/amplitude channels are
        then assumed to be successive channels.
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
        self.config = Config(channel_base, self.core)
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
