from artiq.coredevice.rtio import rtio_output
from artiq.experiment import *
from artiq.coredevice import spi2
from artiq.language.core import kernel, delay
from artiq.language.units import us

class DDS:
    """Shuttler Core DDS spline.

    A Shuttler channel can generate a waveform `w(t)` that is the sum of a
    cubic spline `a(t)` and a sinusoid modulated in amplitude by a cubic
    spline `b(t)` and in phase/frequency by a quadratic spline `c(t)`, where

    .. math::
        w(t) = a(t) + b(t) * cos(c(t))

    and `t` corresponds to time in seconds.
    This class controls the cubic spline `b(t)` and quadratic spline `c(t)`,
    in which

    .. math::
        b(t) &= g * (q_0 + q_1t + \\frac{q_2t^2}{2} + \\frac{q_3t^3}{6})

        c(t) &= r_0 + r_1t + \\frac{r_2t^2}{2}

    `b(t)` is in volts, `c(t)` is in number of turns. Note that `b(t)`
    contributes to a constant gain of :math:`g=1.64676`.

    :param channel: RTIO channel number of this DC-bias spline interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def set_waveform(self, b0: TInt32, b1: TInt32, b2: TInt64, b3: TInt64,
            c0: TInt32, c1: TInt32, c2: TInt32, shift: TInt32 = 0):
        """Set the DDS spline waveform.

        The shift parameter controls the spline update rate:
        - shift = 0: normal rate (no division)
        - shift = 1: half rate (2x longer duration)
        - shift = 2: quarter rate (4x longer duration)
        - ...
        - shift = 15: 1/32768 rate (32768x longer duration)

        Given `b(t)` and `c(t)` as defined in :class:`DDS`, the coefficients
        should be configured by the following formulae.

        .. math::
            T &= 8*10^{-9}

            b_0 &= q_0

            b_1 &= q_1T + \\frac{q_2T^2}{2} + \\frac{q_3T^3}{6}

            b_2 &= q_2T^2 + q_3T^3

            b_3 &= q_3T^3

            c_0 &= r_0

            c_1 &= r_1T + \\frac{r_2T^2}{2}

            c_2 &= r_2T^2

        :math:`b_0`, :math:`b_1`, :math:`b_2` and :math:`b_3` are 16, 32, 48
        and 48 bits in width respectively. See :meth:`shuttler_volt_to_mu` for
        machine unit conversion. :math:`c_0`, :math:`c_1` and :math:`c_2` are
        16, 32 and 32 bits in width respectively.

        Note: The waveform is not updated to the Shuttler Core until
        triggered. See :class:`Trigger` for the update triggering mechanism.

        :param b0: The :math:`b_0` coefficient in machine units.
        :param b1: The :math:`b_1` coefficient in machine units.
        :param b2: The :math:`b_2` coefficient in machine units.
        :param b3: The :math:`b_3` coefficient in machine units.
        :param c0: The :math:`c_0` coefficient in machine units.
        :param c1: The :math:`c_1` coefficient in machine units.
        :param c2: The :math:`c_2` coefficient in machine units.
        :param shift: Clock division factor (0-15). Defaults to 0 (no division).
        """

        if shift < 0 or shift > 15:
            raise ValueError("Shift must be between 0 and 15")

        phase_msb = (c0 >> 2) & 0xFFFF   # Upper 16 bits of 18-bit phase value
        phase_lsb = c0 & 0x3             # Bottom 2 bits of 18-bit phase value

        coef_words = [
            b0 & 0xFFFF,                          # Word 0: amplitude offset
            b1 & 0xFFFF,                          # Word 1: damp low
            (b1 >> 16) & 0xFFFF,                  # Word 2: damp high
            b2 & 0xFFFF,                          # Word 3: ddamp low
            (b2 >> 16) & 0xFFFF,                  # Word 4: ddamp mid
            (b2 >> 32) & 0xFFFF,                  # Word 5: ddamp high
            b3 & 0xFFFF,                          # Word 6: dddamp low
            (b3 >> 16) & 0xFFFF,                  # Word 7: dddamp mid
            (b3 >> 32) & 0xFFFF,                  # Word 8: dddamp high

            phase_msb,                            # Word 9: phase offset main (16 bits)
            c1 & 0xFFFF,                          # Word 10: ftw low
            (c1 >> 16) & 0xFFFF,                  # Word 11: ftw high
            c2 & 0xFFFF,                          # Word 12: chirp low
            (c2 >> 16) & 0xFFFF,                  # Word 13: chirp high

            shift | (phase_lsb << 4),             # Word 14: shift[3:0] + phase_lsb[5:4] + reserved[15:6]
        ]

        for i in range(len(coef_words)):
            rtio_output(self.target_o | i, coef_words[i])
            delay_mu(int64(self.core.ref_multiplier))


class Trigger:
    """Shuttler Core spline coefficients update trigger.

    :param channel: RTIO channel number of the trigger interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def trigger(self, trig_out):
        """Triggers coefficient update of (a) Shuttler Core channel(s).

        Each bit corresponds to a Shuttler waveform generator core. Setting
        ``trig_out`` bits commits the pending coefficient update (from
        ``set_waveform`` in :class:`DCBias` and :class:`DDS`) to the Shuttler Core
        synchronously.

        :param trig_out: Coefficient update trigger bits. The MSB corresponds
            to Channel 15, LSB corresponds to Channel 0.
        """
        rtio_output(self.target_o, trig_out)

class Clear:
    """Shuttler Core clear signal.

    :param channel: RTIO channel number of the clear interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def clear(self, clear_out):
        """Clears the Shuttler Core channel(s).

        Each bit corresponds to a Shuttler waveform generator core. Setting
        ``clear_out`` bits clears the corresponding channels in the Shuttler Core
        synchronously.

        :param clear_out: Clear signal bits. The MSB corresponds
            to Channel 15, LSB corresponds to Channel 0.
        """
        rtio_output(self.target_o, clear_out)

class Reset:
    """Shuttler Core reset signal.

    :param channel: RTIO channel number of the clear interface.
    :param core_device: Core device name.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def reset(self, reset):
        """Resets the LTC2000 DAC.

        :param reset: Reset signal.
        """
        rtio_output(self.target_o, reset)

class Gain:
    """LTC2000 sub DDS gain control.

    Not yet fully implemented.
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8
