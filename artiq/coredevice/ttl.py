"""
Drivers for TTL signals on RTIO.

TTL channels (including the clock generator) all support output event
replacement. For example, pulses of "zero" length (e.g. ``on()``
immediately followed by ``off()``, without a delay) are suppressed.
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
    kernel_invariants = {"core", "channel"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel

        # in RTIO cycles
        self.o_previous_timestamp = numpy.int64(0)

    @kernel
    def output(self):
        pass

    @kernel
    def set_o(self, o):
        rtio_output(now_mu(), self.channel, 0, 1 if o else 0)
        self.o_previous_timestamp = now_mu()

    @kernel
    def sync(self):
        """Busy-wait until all programmed level switches have been
        effected."""
        while self.core.get_rtio_counter_mu() < self.o_previous_timestamp:
            pass

    @kernel
    def on(self):
        """Sets the output to a logic high state at the current position
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
    signal, you must call ``output``. If the channel is in output mode most of
    the time in your setup, it is a good idea to call ``output`` in the
    startup kernel.

    There are three input APIs: gating, sampling and watching. When one
    API is active (e.g. the gate is open, or the input events have not been
    fully read out), another API must not be used simultaneously.

    :param channel: channel number
    """
    kernel_invariants = {"core", "channel"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel

        # in RTIO cycles
        self.o_previous_timestamp = numpy.int64(0)
        self.i_previous_timestamp = numpy.int64(0)
        self.queued_samples = 0

    @kernel
    def set_oe(self, oe):
        rtio_output(now_mu(), self.channel, 1, 1 if oe else 0)

    @kernel
    def output(self):
        """Set the direction to output at the current position of the time
        cursor.

        There must be a delay of at least one RTIO clock cycle before any
        other command can be issued."""
        self.set_oe(True)

    @kernel
    def input(self):
        """Set the direction to input at the current position of the time
        cursor.

        There must be a delay of at least one RTIO clock cycle before any
        other command can be issued."""
        self.set_oe(False)

    @kernel
    def set_o(self, o):
        rtio_output(now_mu(), self.channel, 0, 1 if o else 0)
        self.o_previous_timestamp = now_mu()

    @kernel
    def sync(self):
        """Busy-wait until all programmed level switches have been
        effected."""
        while self.core.get_rtio_counter_mu() < self.o_previous_timestamp:
            pass

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
        """Pulses the output high for the specified duration
        (in machine units).

        The time cursor is advanced by the specified duration."""
        self.on()
        delay_mu(duration)
        self.off()

    @kernel
    def pulse(self, duration):
        """Pulses the output high for the specified duration
        (in seconds).

        The time cursor is advanced by the specified duration."""
        self.on()
        delay(duration)
        self.off()

    # Input API: gating
    @kernel
    def _set_sensitivity(self, value):
        rtio_output(now_mu(), self.channel, 2, value)
        self.i_previous_timestamp = now_mu()

    @kernel
    def gate_rising_mu(self, duration):
        """Register rising edge events for the specified duration
        (in machine units).

        The time cursor is advanced by the specified duration."""
        self._set_sensitivity(1)
        delay_mu(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_falling_mu(self, duration):
        """Register falling edge events for the specified duration
        (in machine units).

        The time cursor is advanced by the specified duration."""
        self._set_sensitivity(2)
        delay_mu(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_both_mu(self, duration):
        """Register both rising and falling edge events for the specified
        duration (in machine units).

        The time cursor is advanced by the specified duration."""
        self._set_sensitivity(3)
        delay_mu(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_rising(self, duration):
        """Register rising edge events for the specified duration
        (in seconds).

        The time cursor is advanced by the specified duration."""
        self._set_sensitivity(1)
        delay(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_falling(self, duration):
        """Register falling edge events for the specified duration
        (in seconds).

        The time cursor is advanced by the specified duration."""
        self._set_sensitivity(2)
        delay(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_both(self, duration):
        """Register both rising and falling edge events for the specified
        duration (in seconds).

        The time cursor is advanced by the specified duration."""
        self._set_sensitivity(3)
        delay(duration)
        self._set_sensitivity(0)

    @kernel
    def count(self):
        """Poll the RTIO input during all the previously programmed gate
        openings, and returns the number of registered events.

        This function does not interact with the time cursor."""
        count = 0
        while rtio_input_timestamp(self.i_previous_timestamp, self.channel) >= 0:
            count += 1
        return count

    @kernel
    def timestamp_mu(self):
        """Poll the RTIO input and returns an event timestamp (in machine
        units), according to the gating.

        If the gate is permanently closed, returns a negative value.

        This function does not interact with the time cursor."""
        return rtio_input_timestamp(self.i_previous_timestamp, self.channel)

    # Input API: sampling
    @kernel
    def sample_input(self):
        """Instructs the RTIO core to read the value of the TTL input at the
        position of the time cursor.

        The time cursor is not modified by this function."""
        rtio_output(now_mu(), self.channel, 3, 0)

    @kernel
    def sample_get(self):
        """Returns the value of a sample previously obtained with
        ``sample_input``.

        Multiple samples may be queued (using multiple calls to
        ``sample_input``) into the RTIO FIFOs and subsequently read out using
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
        of the time cursor and keep checking until ``watch_done``
        is called.

        Returns ``True`` if the input is high. A call to this function
        must always be followed by an eventual call to ``watch_done``
        (use e.g. a try/finally construct to ensure this).

        The time cursor is not modified by this function.
        """
        rtio_output(now_mu(), self.channel, 3, 2)  # gate falling
        return rtio_input_data(self.channel) == 1

    @kernel
    def watch_stay_off(self):
        """Like ``watch_stay_on``, but for low levels."""
        rtio_output(now_mu(), self.channel, 3, 1)  # gate rising
        return rtio_input_data(self.channel) == 0

    @kernel
    def watch_done(self):
        """Stop watching the input at the position of the time cursor.

        Returns ``True`` if the input has not changed state while it
        was being watched.

        The time cursor is not modified by this function. This function
        always makes the slack negative.
        """
        rtio_output(now_mu(), self.channel, 2, 0)
        success = True
        try:
            while rtio_input_timestamp(now_mu(), self.channel) != -1:
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
    """
    kernel_invariants = {"core", "channel", "acc_width"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel

        # in RTIO cycles
        self.previous_timestamp = numpy.int64(0)
        self.acc_width = numpy.int64(24)

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
        rtio_output(now_mu(), self.channel, 0, frequency)
        self.previous_timestamp = now_mu()

    @kernel
    def set(self, frequency):
        """Like ``set_mu``, but using Hz."""
        self.set_mu(self.frequency_to_ftw(frequency))

    @kernel
    def stop(self):
        """Stop the toggling of the clock and set the output level to 0."""
        self.set_mu(0)

    @kernel
    def sync(self):
        """Busy-wait until all programmed frequency switches and stops have
        been effected."""
        while self.core.get_rtio_counter_mu() < self.o_previous_timestamp:
            pass
