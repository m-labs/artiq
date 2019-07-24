"""
Drivers for TTL signals on RTIO.

TTL channels (including the clock generator) all support output event
replacement. For example, pulses of "zero" length (e.g. :meth:`TTLInOut.on`
immediately followed by :meth:`TTLInOut.off`, without a delay) are suppressed.
"""

import numpy

from artiq.language.core import *
from artiq.language.types import *
from artiq.coredevice.rtio import (rtio_output, rtio_input_timestamp,
                                   rtio_input_data)
from artiq.coredevice.exceptions import RTIOOverflow


# RTIO TTL address map:
# 0 Output level
# 1 Output enable
# 2 Set input sensitivity
# 3 Set input sensitivity and sample


class TTLOut:
    """RTIO TTL output driver.

    This should be used with output-only channels.

    :param channel: channel number
    """
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def output(self):
        pass

    @kernel
    def set_o(self, o):
        rtio_output(self.target_o, 1 if o else 0)

    @kernel
    def on(self):
        """Set the output to a logic high state at the current position
        of the time cursor.

        The time cursor is not modified by this function."""
        self.set_o(True)

    @kernel
    def off(self):
        """Set the output to a logic low state at the current position
        of the time cursor.

        The time cursor is not modified by this function."""
        self.set_o(False)

    @kernel
    def pulse_mu(self, duration):
        """Pulse the output high for the specified duration
        (in machine units).

        The time cursor is advanced by the specified duration."""
        self.on()
        delay_mu(duration)
        self.off()

    @kernel
    def pulse(self, duration):
        """Pulse the output high for the specified duration
        (in seconds).

        The time cursor is advanced by the specified duration."""
        self.on()
        delay(duration)
        self.off()


class TTLInOut:
    """RTIO TTL input/output driver.

    In output mode, provides functions to set the logic level on the signal.

    In input mode, provides functions to analyze the incoming signal, with
    real-time gating to prevent overflows.

    RTIO TTLs supports zero-length transition suppression. For example, if
    two pulses are emitted back-to-back with no delay between them, they will
    be merged into a single pulse with a duration equal to the sum of the
    durations of the original pulses.

    This should be used with bidirectional channels.

    Note that the channel is in input mode by default. If you need to drive a
    signal, you must call :meth:`output`. If the channel is in output mode most of
    the time in your setup, it is a good idea to call :meth:`output` in the
    startup kernel.

    There are three input APIs: gating, sampling and watching. When one
    API is active (e.g. the gate is open, or the input events have not been
    fully read out), another API must not be used simultaneously.

    :param channel: channel number
    """
    kernel_invariants = {"core", "channel", "gate_latency_mu",
        "target_o", "target_oe", "target_sens", "target_sample"}

    def __init__(self, dmgr, channel, gate_latency_mu=None,
                 core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel

        # With TTLs inputs, the gate control is connected to a high-latency
        # path through SED. When looking at the RTIO counter to determine if
        # the gate has closed, we need to take this latency into account.
        # See: https://github.com/m-labs/artiq/issues/1137
        if gate_latency_mu is None:
            gate_latency_mu = 13*self.core.ref_multiplier
        self.gate_latency_mu = gate_latency_mu

        self.target_o      = (channel << 8) + 0
        self.target_oe     = (channel << 8) + 1
        self.target_sens   = (channel << 8) + 2
        self.target_sample = (channel << 8) + 3

    @kernel
    def set_oe(self, oe):
        rtio_output(self.target_oe, 1 if oe else 0)

    @kernel
    def output(self):
        """Set the direction to output at the current position of the time
        cursor.

        There must be a delay of at least one RTIO clock cycle before any
        other command can be issued.

        This method only configures the direction at the FPGA. When using
        buffered I/O interfaces, such as the Sinara TTL cards, the buffer
        direction must be configured separately in the hardware."""
        self.set_oe(True)

    @kernel
    def input(self):
        """Set the direction to input at the current position of the time
        cursor.

        There must be a delay of at least one RTIO clock cycle before any
        other command can be issued.

        This method only configures the direction at the FPGA. When using
        buffered I/O interfaces, such as the Sinara TTL cards, the buffer
        direction must be configured separately in the hardware."""
        self.set_oe(False)

    @kernel
    def set_o(self, o):
        rtio_output(self.target_o, 1 if o else 0)

    @kernel
    def on(self):
        """Set the output to a logic high state at the current position of the
        time cursor.

        The channel must be in output mode.

        The time cursor is not modified by this function."""
        self.set_o(True)

    @kernel
    def off(self):
        """Set the output to a logic low state at the current position of the
        time cursor.

        The channel must be in output mode.

        The time cursor is not modified by this function."""
        self.set_o(False)

    @kernel
    def pulse_mu(self, duration):
        """Pulse the output high for the specified duration
        (in machine units).

        The time cursor is advanced by the specified duration."""
        self.on()
        delay_mu(duration)
        self.off()

    @kernel
    def pulse(self, duration):
        """Pulse the output high for the specified duration
        (in seconds).

        The time cursor is advanced by the specified duration."""
        self.on()
        delay(duration)
        self.off()

    # Input API: gating
    @kernel
    def _set_sensitivity(self, value):
        rtio_output(self.target_sens, value)

    @kernel
    def gate_rising_mu(self, duration):
        """Register rising edge events for the specified duration
        (in machine units).

        The time cursor is advanced by the specified duration.

        :return: The timeline cursor at the end of the gate window, for
            convenience when used with :meth:`count`/:meth:`timestamp_mu`.
        """
        self._set_sensitivity(1)
        delay_mu(duration)
        self._set_sensitivity(0)
        return now_mu()

    @kernel
    def gate_falling_mu(self, duration):
        """Register falling edge events for the specified duration
        (in machine units).

        The time cursor is advanced by the specified duration.

        :return: The timeline cursor at the end of the gate window, for
            convenience when used with :meth:`count`/:meth:`timestamp_mu`.
        """
        self._set_sensitivity(2)
        delay_mu(duration)
        self._set_sensitivity(0)
        return now_mu()

    @kernel
    def gate_both_mu(self, duration):
        """Register both rising and falling edge events for the specified
        duration (in machine units).

        The time cursor is advanced by the specified duration.

        :return: The timeline cursor at the end of the gate window, for
            convenience when used with :meth:`count`/:meth:`timestamp_mu`.
        """
        self._set_sensitivity(3)
        delay_mu(duration)
        self._set_sensitivity(0)
        return now_mu()

    @kernel
    def gate_rising(self, duration):
        """Register rising edge events for the specified duration
        (in seconds).

        The time cursor is advanced by the specified duration.

        :return: The timeline cursor at the end of the gate window, for
            convenience when used with :meth:`count`/:meth:`timestamp_mu`.
        """
        self._set_sensitivity(1)
        delay(duration)
        self._set_sensitivity(0)
        return now_mu()

    @kernel
    def gate_falling(self, duration):
        """Register falling edge events for the specified duration
        (in seconds).

        The time cursor is advanced by the specified duration.

        :return: The timeline cursor at the end of the gate window, for
            convenience when used with :meth:`count`/:meth:`timestamp_mu`.

        """
        self._set_sensitivity(2)
        delay(duration)
        self._set_sensitivity(0)
        return now_mu()

    @kernel
    def gate_both(self, duration):
        """Register both rising and falling edge events for the specified
        duration (in seconds).

        The time cursor is advanced by the specified duration.

        :return: The timeline cursor at the end of the gate window, for
            convenience when used with :meth:`count`/:meth:`timestamp_mu`.
        """
        self._set_sensitivity(3)
        delay(duration)
        self._set_sensitivity(0)
        return now_mu()

    @kernel
    def count(self, up_to_timestamp_mu):
        """Consume RTIO input events until the hardware timestamp counter has
        reached the specified timestamp and return the number of observed
        events.

        This function does not interact with the timeline cursor.

        See the ``gate_*()`` family of methods to select the input transitions
        that generate events, and :meth:`timestamp_mu` to obtain the timestamp
        of the first event rather than an accumulated count.

        :param up_to_timestamp_mu: The timestamp up to which execution is
            blocked, that is, up to which input events are guaranteed to be
            taken into account. (Events with later timestamps might still be
            registered if they are already available.)

        :return: The number of events before the timeout elapsed (0 if none
            observed).

        Examples:
            To count events on channel ``ttl_input``, up to the current timeline
            position::

                ttl_input.count(now_mu())

            If other events are scheduled between the end of the input gate
            period and when the number of events is counted, using ``now_mu()``
            as timeout consumes an unnecessary amount of timeline slack. In
            such cases, it can be beneficial to pass a more precise timestamp,
            for example::

                gate_end_mu = ttl_input.gate_rising(100 * us)

                # Schedule a long pulse sequence, represented here by a delay.
                delay(10 * ms)

                # Get number of rising edges. This will block until the end of
                # the gate window, but does not wait for the long pulse sequence
                # afterwards, thus (likely) completing with a large amount of
                # slack left.
                num_rising_edges = ttl_input.count(gate_end_mu)

            The ``gate_*()`` family of methods return the cursor at the end
            of the window, allowing this to be expressed in a compact fashion::

                ttl_input.count(ttl_input.gate_rising(100 * us))
        """
        count = 0
        while rtio_input_timestamp(up_to_timestamp_mu + self.gate_latency_mu, self.channel) >= 0:
            count += 1
        return count

    @kernel
    def timestamp_mu(self, up_to_timestamp_mu):
        """Return the timestamp of the next RTIO input event, or -1 if the
        hardware timestamp counter reaches the given value before an event is
        received.

        This function does not interact with the timeline cursor.

        See the ``gate_*()`` family of methods to select the input transitions
        that generate events, and :meth:`count` for usage examples.

        :param up_to_timestamp_mu: The timestamp up to which execution is
            blocked, that is, up to which input events are guaranteed to be
            taken into account. (Events with later timestamps might still be
            registered if they are already available.)

        :return: The timestamp (in machine units) of the first event received;
            -1 on timeout.
        """
        return rtio_input_timestamp(up_to_timestamp_mu + self.gate_latency_mu, self.channel)

    # Input API: sampling
    @kernel
    def sample_input(self):
        """Instructs the RTIO core to read the value of the TTL input at the
        position of the time cursor.

        The time cursor is not modified by this function."""
        rtio_output(self.target_sample, 0)

    @kernel
    def sample_get(self):
        """Returns the value of a sample previously obtained with
        :meth:`sample_input`.

        Multiple samples may be queued (using multiple calls to
        :meth:`sample_input`) into the RTIO FIFOs and subsequently read out using
        multiple calls to this function.

        This function does not interact with the time cursor."""
        return rtio_input_data(self.channel)

    @kernel
    def sample_get_nonrt(self):
        """Convenience function that obtains the value of a sample
        at the position of the time cursor, breaks realtime, and
        returns the sample value."""
        self.sample_input()
        r = self.sample_get()
        self.core.break_realtime()
        return r

    # Input API: watching
    @kernel
    def watch_stay_on(self):
        """Checks that the input is at a high level at the position
        of the time cursor and keep checking until :meth:`watch_done`
        is called.

        Returns ``True`` if the input is high. A call to this function
        must always be followed by an eventual call to :meth:`watch_done`
        (use e.g. a try/finally construct to ensure this).

        The time cursor is not modified by this function.
        """
        rtio_output(self.target_sample, 2)  # gate falling
        return rtio_input_data(self.channel) == 1

    @kernel
    def watch_stay_off(self):
        """Like :meth:`watch_stay_on`, but for low levels."""
        rtio_output(self.target_sample, 1)  # gate rising
        return rtio_input_data(self.channel) == 0

    @kernel
    def watch_done(self):
        """Stop watching the input at the position of the time cursor.

        Returns ``True`` if the input has not changed state while it
        was being watched.

        The time cursor is not modified by this function. This function
        always makes the slack negative.
        """
        rtio_output(self.target_sens, 0)
        success = True
        try:
            while rtio_input_timestamp(now_mu() + self.gate_latency_mu, self.channel) != -1:
                success = False
        except RTIOOverflow:
            success = False
        return success


class TTLClockGen:
    """RTIO TTL clock generator driver.

    This should be used with TTL channels that have a clock generator
    built into the gateware (not compatible with regular TTL channels).

    The time cursor is not modified by any function in this class.

    :param channel: channel number
    :param acc_width: accumulator width in bits
    """
    kernel_invariants = {"core", "channel", "target", "acc_width"}

    def __init__(self, dmgr, channel, acc_width=24, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target = channel << 8

        self.acc_width = numpy.int64(acc_width)

    @portable
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.
        """
        return round(2**self.acc_width*frequency*self.core.coarse_ref_period)

    @portable
    def ftw_to_frequency(self, ftw):
        """Returns the frequency corresponding to the given frequency tuning
        word.
        """
        return ftw/self.core.coarse_ref_period/2**self.acc_width

    @kernel
    def set_mu(self, frequency):
        """Set the frequency of the clock, in machine units, at the current
        position of the time cursor.

        This also sets the phase, as the time of the first generated rising
        edge corresponds to the time of the call.

        The clock generator contains a 24-bit phase accumulator operating on
        the RTIO clock. At each RTIO clock tick, the frequency tuning word is
        added to the phase accumulator. The most significant bit of the phase
        accumulator is connected to the TTL line. Setting the frequency tuning
        word has the additional effect of setting the phase accumulator to
        0x800000.

        Due to the way the clock generator operates, frequency tuning words
        that are not powers of two cause jitter of one RTIO clock cycle at the
        output."""
        rtio_output(self.target, frequency)

    @kernel
    def set(self, frequency):
        """Like :meth:`set_mu`, but using Hz."""
        self.set_mu(self.frequency_to_ftw(frequency))

    @kernel
    def stop(self):
        """Stop the toggling of the clock and set the output level to 0."""
        self.set_mu(0)
