from artiq.language.core import *


class TTLOut:
    """RTIO TTL output driver.

    This should be used with output-only channels.

    :param core: core device
    :param channel: channel number
    """
    def __init__(self, dmgr, channel):
        self.core = dmgr.get("core")
        self.channel = channel

        # in RTIO cycles
        self.o_previous_timestamp = int64(0)

    @kernel
    def set_o(self, o):
        syscall("ttl_set_o", now_mu(), self.channel, o)
        self.o_previous_timestamp = now_mu()

    @kernel
    def sync(self):
        """Busy-wait until all programmed level switches have been
        effected."""
        while syscall("rtio_get_counter") < self.o_previous_timestamp:
            pass

    @kernel
    def on(self):
        """Sets the output to a logic high state."""
        self.set_o(True)

    @kernel
    def off(self):
        """Set the output to a logic low state."""
        self.set_o(False)

    @kernel
    def pulse_mu(self, duration):
        """Pulse the output high for the specified duration
        (in machine units)."""
        self.on()
        delay_mu(duration)
        self.off()

    @kernel
    def pulse(self, duration):
        """Pulse the output high for the specified duration
        (in seconds)."""
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

    :param core: core device
    :param channel: channel number
    """
    def __init__(self, dmgr, channel):
        self.core = dmgr.get("core")
        self.channel = channel

        # in RTIO cycles
        self.o_previous_timestamp = int64(0)
        self.i_previous_timestamp = int64(0)

    @kernel
    def set_oe(self, oe):
        syscall("ttl_set_oe", now_mu(), self.channel, oe)

    @kernel
    def output(self):
        self.set_oe(True)

    @kernel
    def input(self):
        self.set_oe(False)

    @kernel
    def set_o(self, o):
        syscall("ttl_set_o", now_mu(), self.channel, o)
        self.o_previous_timestamp = now_mu()

    @kernel
    def sync(self):
        """Busy-wait until all programmed level switches have been
        effected."""
        while syscall("rtio_get_counter") < self.o_previous_timestamp:
            pass

    @kernel
    def on(self):
        """Set the output to a logic high state."""
        self.set_o(True)

    @kernel
    def off(self):
        """Set the output to a logic low state."""
        self.set_o(False)

    @kernel
    def pulse_mu(self, duration):
        """Pulses the output high for the specified duration
        (in machine units)."""
        self.on()
        delay_mu(duration)
        self.off()

    @kernel
    def pulse(self, duration):
        """Pulses the output high for the specified duration
        (in seconds)."""
        self.on()
        delay(duration)
        self.off()

    @kernel
    def _set_sensitivity(self, value):
        syscall("ttl_set_sensitivity", now_mu(), self.channel, value)
        self.i_previous_timestamp = now_mu()

    @kernel
    def gate_rising_mu(self, duration):
        """Register rising edge events for the specified duration
        (in machine units)."""
        self._set_sensitivity(1)
        delay_mu(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_falling_mu(self, duration):
        """Register falling edge events for the specified duration
        (in machine units)."""
        self._set_sensitivity(2)
        delay_mu(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_both_mu(self, duration):
        """Register both rising and falling edge events for the specified
        duration (in machine units)."""
        self._set_sensitivity(3)
        delay_mu(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_rising(self, duration):
        """Register rising edge events for the specified duration
        (in seconds)."""
        self._set_sensitivity(1)
        delay(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_falling(self, duration):
        """Register falling edge events for the specified duration
        (in seconds)."""
        self._set_sensitivity(2)
        delay(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_both(self, duration):
        """Register both rising and falling edge events for the specified
        duration (in seconds)."""
        self._set_sensitivity(3)
        delay(duration)
        self._set_sensitivity(0)

    @kernel
    def count(self):
        """Poll the RTIO input during all the previously programmed gate
        openings, and returns the number of registered events."""
        count = 0
        while syscall("ttl_get", self.channel,
                      self.i_previous_timestamp) >= 0:
            count += 1
        return count

    @kernel
    def timestamp_mu(self):
        """Poll the RTIO input and returns an event timestamp (in machine
        units), according to the gating.

        If the gate is permanently closed, returns a negative value.
        """
        return syscall("ttl_get", self.channel, self.i_previous_timestamp)


class TTLClockGen:
    """RTIO TTL clock generator driver.

    This should be used with TTL channels that have a clock generator
    built into the gateware (not compatible with regular TTL channels).

    :param core: core device
    :param channel: channel number
    """
    def __init__(self, dmgr, channel):
        self.core = dmgr.get("core")
        self.channel = channel

    def build(self):
        # in RTIO cycles
        self.previous_timestamp = int64(0)
        self.acc_width = 24

    @portable
    def frequency_to_ftw(self, frequency):
        """Returns the frequency tuning word corresponding to the given
        frequency.
        """
        return round(2**self.acc_width*frequency*self.core.ref_period)

    @portable
    def ftw_to_frequency(self, ftw):
        """Returns the frequency corresponding to the given frequency tuning
        word.
        """
        return ftw/self.core.ref_period/2**self.acc_width

    @kernel
    def set_mu(self, frequency):
        """Set the frequency of the clock, in machine units.

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
        output.
        """
        syscall("ttl_clock_set", now_mu(), self.channel, frequency)
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
        while syscall("rtio_get_counter") < self.o_previous_timestamp:
            pass
