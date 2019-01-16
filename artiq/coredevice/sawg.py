"""
Driver for the Smart Arbitrary Waveform Generator (SAWG) on RTIO.

The SAWG is an "improved DDS" built in gateware and interfacing to
high-speed DACs.

Output event replacement is supported except on the configuration channel.
"""


from artiq.language.types import TInt32, TFloat
from numpy import int32, int64
from artiq.language.core import kernel
from artiq.coredevice.spline import Spline
from artiq.coredevice.rtio import rtio_output


# sawg.Config addresses
_SAWG_DIV = 0
_SAWG_CLR = 1
_SAWG_IQ_EN = 2
# _SAWF_PAD = 3  # reserved
_SAWG_OUT_MIN = 4
_SAWG_OUT_MAX = 5
_SAWG_DUC_MIN = 6
_SAWG_DUC_MAX = 7


class Config:
    """SAWG configuration.

    Exposes the configurable quantities of a single SAWG channel.

    Access to the configuration registers for a SAWG channel can not
    be concurrent. There must be at least :attr:`_rtio_interval` machine
    units of delay between accesses. Replacement is not supported and will be
    lead to an ``RTIOCollision`` as this is likely a programming error.
    All methods therefore advance the timeline by the duration of one
    configuration register transfer.

    :param channel: RTIO channel number of the channel.
    :param core: Core device.
    """
    kernel_invariants = {"channel", "core", "_out_scale", "_duc_scale",
            "_rtio_interval"}

    def __init__(self, channel, core, cordic_gain=1.):
        self.channel = channel
        self.core = core
        # normalized DAC output
        self._out_scale = (1 << 15) - 1.
        # normalized DAC output including DUC cordic gain
        self._duc_scale = self._out_scale/cordic_gain
        # configuration channel access interval
        self._rtio_interval = int64(3*self.core.ref_multiplier)

    @kernel
    def set_div(self, div: TInt32, n: TInt32=0):
        """Set the spline evolution divider and current counter value.

        The divider and the spline evolution are synchronized across all
        spline channels within a SAWG channel. The DDS/DUC phase accumulators
        always evolves at full speed.

        .. note:: The spline evolution divider has not been tested extensively
            and is currently considered a technological preview only.

        :param div: Spline evolution divider, such that
            ``t_sawg_spline/t_rtio_coarse = div + 1``. Default: ``0``.
        :param n: Current value of the counter. Default: ``0``.
        """
        rtio_output((self.channel << 8) | _SAWG_DIV, div | (n << 16))
        delay_mu(self._rtio_interval)

    @kernel
    def set_clr(self, clr0: TInt32, clr1: TInt32, clr2: TInt32):
        """Set the accumulator clear mode for the three phase accumulators.

        When the ``clr`` bit for a given DDS/DUC phase accumulator is
        set, that phase accumulator will be cleared with every phase offset
        RTIO command and the output phase of the DDS/DUC will be
        exactly the phase RTIO value ("absolute phase update mode").

        .. math::
            q^\prime(t) = p^\prime + (t - t^\prime) f^\prime

        In turn, when the bit is cleared, the phase RTIO channels
        determine a phase offset to the current (carrier-) value of the
        DDS/DUC phase accumulator. This "relative phase update mode" is
        sometimes also called “continuous phase mode”.

        .. math::
            q^\prime(t) = q(t^\prime) + (p^\prime - p) +
                (t - t^\prime) f^\prime

        Where:

            * :math:`q`, :math:`q^\prime`: old/new phase accumulator
            * :math:`p`, :math:`p^\prime`: old/new phase offset
            * :math:`f^\prime`: new frequency
            * :math:`t^\prime`: timestamp of setting new :math:`p`, :math:`f`
            * :math:`t`: running time

        :param clr0: Auto-clear phase accumulator of the ``phase0``/
          ``frequency0`` DUC. Default: ``True``
        :param clr1: Auto-clear phase accumulator of the ``phase1``/
          ``frequency1`` DDS. Default: ``True``
        :param clr2: Auto-clear phase accumulator of the ``phase2``/
          ``frequency2`` DDS. Default: ``True``
        """
        rtio_output((self.channel << 8) | _SAWG_CLR, clr0 |
                (clr1 << 1) | (clr2 << 2))
        delay_mu(self._rtio_interval)

    @kernel
    def set_iq_en(self, i_enable: TInt32, q_enable: TInt32):
        """Enable I/Q data on this DAC channel.

        Every pair of SAWG channels forms a buddy pair.
        The ``iq_en`` configuration controls which DDS data is emitted to the
        DACs.

        Refer to the documentation of :class:`SAWG` for a mathematical
        description of ``i_enable`` and ``q_enable``.

        .. note:: Quadrature data from the buddy channel is currently
            a technological preview only. The data is ignored in the SAWG
            gateware and not added to the DAC output.
            This is equivalent to the ``q_enable`` switch always being ``0``.

        :param i_enable: Controls adding the in-phase
              DUC-DDS data of *this* SAWG channel to *this* DAC channel.
              Default: ``1``.
        :param q_enable: controls adding the quadrature
              DUC-DDS data of this SAWG's *buddy* channel to *this* DAC
              channel. Default: ``0``.
        """
        rtio_output((self.channel << 8) | _SAWG_IQ_EN, i_enable |
                (q_enable << 1))
        delay_mu(self._rtio_interval)

    @kernel
    def set_duc_max_mu(self, limit: TInt32):
        """Set the digital up-converter (DUC) I and Q data summing junctions
        upper limit. In machine units.

        The default limits are chosen to reach maximum and minimum DAC output
        amplitude.

        For a description of the limiter functions in normalized units see:

        .. seealso:: :meth:`set_duc_max`
        """
        rtio_output((self.channel << 8) | _SAWG_DUC_MAX, limit)
        delay_mu(self._rtio_interval)

    @kernel
    def set_duc_min_mu(self, limit: TInt32):
        """.. seealso:: :meth:`set_duc_max_mu`"""
        rtio_output((self.channel << 8) | _SAWG_DUC_MIN, limit)
        delay_mu(self._rtio_interval)

    @kernel
    def set_out_max_mu(self, limit: TInt32):
        """.. seealso:: :meth:`set_duc_max_mu`"""
        rtio_output((self.channel << 8) | _SAWG_OUT_MAX, limit)
        delay_mu(self._rtio_interval)

    @kernel
    def set_out_min_mu(self, limit: TInt32):
        """.. seealso:: :meth:`set_duc_max_mu`"""
        rtio_output((self.channel << 8) | _SAWG_OUT_MIN, limit)
        delay_mu(self._rtio_interval)

    @kernel
    def set_duc_max(self, limit: TFloat):
        """Set the digital up-converter (DUC) I and Q data summing junctions
        upper limit.

        Each of the three summing junctions has a saturating adder with
        configurable upper and lower limits. The three summing junctions are:

            * At the in-phase input to the ``phase0``/``frequency0`` fast DUC,
              after the anti-aliasing FIR filter.
            * At the quadrature input to the ``phase0``/``frequency0``
              fast DUC, after the anti-aliasing FIR filter. The in-phase and
              quadrature data paths both use the same limits.
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

        :param limit: Limit value ``[-1, 1]``. The output of the limiter will
            never exceed this limit. The default limits are the full range
            ``[-1, 1]``.

        .. seealso::
            * :meth:`set_duc_max`: Upper limit of the in-phase and quadrature
              inputs to the DUC.
            * :meth:`set_duc_min`: Lower limit of the in-phase and quadrature
              inputs to the DUC.
            * :meth:`set_out_max`: Upper limit of the DAC output.
            * :meth:`set_out_min`: Lower limit of the DAC output.
        """
        self.set_duc_max_mu(int32(round(limit*self._duc_scale)))

    @kernel
    def set_duc_min(self, limit: TFloat):
        """.. seealso:: :meth:`set_duc_max`"""
        self.set_duc_min_mu(int32(round(limit*self._duc_scale)))

    @kernel
    def set_out_max(self, limit: TFloat):
        """.. seealso:: :meth:`set_duc_max`"""
        self.set_out_max_mu(int32(round(limit*self._out_scale)))

    @kernel
    def set_out_min(self, limit: TFloat):
        """.. seealso:: :meth:`set_duc_max`"""
        self.set_out_min_mu(int32(round(limit*self._out_scale)))


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
    (``frequency1``/``phase1`` and ``frequency2``/``phase2``) that are
    executing and sampling at the coarse RTIO frequency. They can represent
    frequencies within the first Nyquist zone from ``-f_rtio_coarse/2`` to
    ``f_rtio_coarse/2``.

    .. note:: The coarse RTIO frequency ``f_rtio_coarse`` is the inverse of
      ``ref_period*multiplier``. Both are arguments of the ``Core`` device,
      specified in the device database ``device_db.py``.

    The sum of their outputs is then interpolated by a factor of
    :attr:`parallelism` (2, 4, 8 depending on the bitstream) using a
    finite-impulse-response (FIR) anti-aliasing filter (more accurately
    a half-band filter).

    The filter is followed by a configurable saturating limiter.

    After the limiter, the data is shifted in frequency using a complex
    digital up-converter (DUC, ``frequency0``/``phase0``) running at
    :attr:`parallelism` times the coarse RTIO frequency. The first Nyquist
    zone of the DUC extends from ``-f_rtio_coarse*parallelism/2`` to
    ``f_rtio_coarse*parallelism/2``. Other Nyquist zones are usable depending
    on the interpolation/modulation options configured in the DAC.

    The real/in-phase data after digital up-conversion can be offset using
    another spline interpolator ``offset``.

    The ``i_enable``/``q_enable`` switches enable emission of quadrature
    signals for later analog quadrature mixing distinguishing upper and lower
    sidebands and thus doubling the bandwidth. They can also be used to emit
    four-tone signals.

    .. note:: Quadrature data from the buddy channel is currently
       ignored in the SAWG gateware and not added to the DAC output.
       This is equivalent to the ``q_enable`` switch always being ``0``.

    The configuration channel and the nine
    :class:`artiq.coredevice.spline.Spline` interpolators are accessible as
    attributes:

    * :attr:`config`: :class:`Config`
    * :attr:`offset`, :attr:`amplitude1`, :attr:`amplitude2`: in units
      of full scale
    * :attr:`phase0`, :attr:`phase1`, :attr:`phase2`: in units of turns
    * :attr:`frequency0`, :attr:`frequency1`, :attr:`frequency2`: in units
      of Hz

    .. note:: The latencies (pipeline depths) of the nine data channels (i.e.
        all except :attr:`config`) are matched. Equivalent channels (e.g.
        :attr:`phase1` and :attr:`phase2`) are exactly matched. Channels of
        different type or functionality (e.g. :attr:`offset` vs
        :attr:`amplitude1`, DDS vs DUC, :attr:`phase0` vs :attr:`phase1`) are
        only matched to within one coarse RTIO cycle.

    :param channel_base: RTIO channel number of the first channel (amplitude).
        The configuration channel and frequency/phase/amplitude channels are
        then assumed to be successive channels.
    :param parallelism: Number of output samples per coarse RTIO clock cycle.
    :param core_device: Name of the core device that this SAWG is on.
    """
    kernel_invariants = {"channel_base", "core", "parallelism",
                         "amplitude1", "frequency1", "phase1",
                         "amplitude2", "frequency2", "phase2",
                         "frequency0", "phase0", "offset"}

    def __init__(self, dmgr, channel_base, parallelism, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel_base = channel_base
        self.parallelism = parallelism
        width = 16
        time_width = 16
        cordic_gain = 1.646760258057163  # Cordic(width=16, guard=None).gain
        head_room = 1.001
        self.config = Config(channel_base, self.core, cordic_gain)
        self.offset = Spline(width, time_width, channel_base + 1,
                             self.core, 2.*head_room)
        self.amplitude1 = Spline(width, time_width, channel_base + 2,
                                 self.core, 2*head_room*cordic_gain**2)
        self.frequency1 = Spline(3*width, time_width, channel_base + 3,
                                 self.core, 1/self.core.coarse_ref_period)
        self.phase1 = Spline(width, time_width, channel_base + 4,
                             self.core, 1.)
        self.amplitude2 = Spline(width, time_width, channel_base + 5,
                                 self.core, 2*head_room*cordic_gain**2)
        self.frequency2 = Spline(3*width, time_width, channel_base + 6,
                                 self.core, 1/self.core.coarse_ref_period)
        self.phase2 = Spline(width, time_width, channel_base + 7,
                             self.core, 1.)
        self.frequency0 = Spline(2*width, time_width, channel_base + 8,
                                 self.core,
                                 parallelism/self.core.coarse_ref_period)
        self.phase0 = Spline(width, time_width, channel_base + 9,
                             self.core, 1.)

    @kernel
    def reset(self):
        """Re-establish initial conditions.

        This clears all spline interpolators, accumulators and configuration
        settings.

        This method advances the timeline by the time required to perform all
        7 writes to the configuration channel, plus 9 coarse RTIO cycles.
        """
        self.config.set_div(0, 0)
        self.config.set_clr(1, 1, 1)
        self.config.set_iq_en(1, 0)
        self.config.set_duc_min(-1.)
        self.config.set_duc_max(1.)
        self.config.set_out_min(-1.)
        self.config.set_out_max(1.)
        self.frequency0.set_mu(0)
        coarse_cycle = int64(self.core.ref_multiplier)
        delay_mu(coarse_cycle)
        self.frequency1.set_mu(0)
        delay_mu(coarse_cycle)
        self.frequency2.set_mu(0)
        delay_mu(coarse_cycle)
        self.phase0.set_mu(0)
        delay_mu(coarse_cycle)
        self.phase1.set_mu(0)
        delay_mu(coarse_cycle)
        self.phase2.set_mu(0)
        delay_mu(coarse_cycle)
        self.amplitude1.set_mu(0)
        delay_mu(coarse_cycle)
        self.amplitude2.set_mu(0)
        delay_mu(coarse_cycle)
        self.offset.set_mu(0)
        delay_mu(coarse_cycle)
