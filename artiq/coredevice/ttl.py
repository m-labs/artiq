from artiq.language.core import *
from artiq.language.db import *


class LLTTLOut(AutoDB):
    """Low-level RTIO TTL output driver.

    Allows setting RTIO TTL outputs at arbitrary times, without time
    unit conversion.

    This is meant to be used mostly in drivers; consider using
    ``TTLOut`` instead.

    This should be used with output-only channels.
    """
    class DBKeys:
        core = Device()
        channel = Argument()

    @kernel
    def set_o(self, t, value):
        """Sets the output value of the RTIO channel.

        :param t: timestamp in RTIO cycles (64-bit integer).
        :param value: value to set at the output.
        """
        syscall("rtio_set_o", t, self.channel, value)

    @kernel
    def on(self, t):
        """Turns the RTIO channel on.

        :param t: timestamp in RTIO cycles (64-bit integer).
        """
        self.set_o(t, True)

    @kernel
    def off(self, t):
        """Turns the RTIO channel off.

        :param t: timestamp in RTIO cycles (64-bit integer).
        """
        self.set_o(t, False)


class TTLOut(AutoDB):
    """RTIO TTL output driver.

    This should be used with output-only channels.

    :param core: core device
    :param channel: channel number
    """
    class DBKeys:
        core = Device()
        channel = Argument()


    def build(self):
        # in RTIO cycles
        self.o_previous_timestamp = int64(0)

    @kernel
    def _set_o(self, o):
        syscall("rtio_set_o", time_to_cycles(now()), self.channel, o)
        self.o_previous_timestamp = time_to_cycles(now())

    @kernel
    def sync(self):
        """Busy-waits until all programmed level switches have been effected."""
        while syscall("rtio_get_counter") < self.o_previous_timestamp:
            pass

    @kernel
    def on(self):
        """Sets the output to a logic high state."""
        self._set_o(True)

    @kernel
    def off(self):
        """Sets the output to a logic low state."""
        self._set_o(False)

    @kernel
    def pulse(self, duration):
        """Pulses the output high for the specified duration."""
        self.on()
        delay(duration)
        self.off()


class TTLInOut(AutoDB):
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
    class DBKeys:
        core = Device()
        channel = Argument()

    def build(self):
        # in RTIO cycles
        self.o_previous_timestamp = int64(0)
        self.i_previous_timestamp = int64(0)

    @kernel
    def _set_oe(self, oe):
        syscall("rtio_set_oe", time_to_cycles(now()), self.channel, oe)

    @kernel
    def output(self):
        self._set_oe(True)

    @kernel
    def input(self):
        self._set_oe(False)

    @kernel
    def _set_o(self, o):
        syscall("rtio_set_o", time_to_cycles(now()), self.channel, o)
        self.o_previous_timestamp = time_to_cycles(now())

    @kernel
    def sync(self):
        """Busy-waits until all programmed level switches have been effected."""
        while syscall("rtio_get_counter") < self.o_previous_timestamp:
            pass

    @kernel
    def on(self):
        """Sets the output to a logic high state."""
        self._set_o(True)

    @kernel
    def off(self):
        """Sets the output to a logic low state."""
        self._set_o(False)

    @kernel
    def pulse(self, duration):
        """Pulses the output high for the specified duration."""
        self.on()
        delay(duration)
        self.off()

    @kernel
    def _set_sensitivity(self, value):
        syscall("rtio_set_sensitivity", time_to_cycles(now()), self.channel, value)
        self.i_previous_timestamp = time_to_cycles(now())

    @kernel
    def gate_rising(self, duration):
        """Register rising edge events for the specified duration."""
        self._set_sensitivity(1)
        delay(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_falling(self, duration):
        """Register falling edge events for the specified duration."""
        self._set_sensitivity(2)
        delay(duration)
        self._set_sensitivity(0)

    @kernel
    def gate_both(self, duration):
        """Register both rising and falling edge events for the specified
        duration."""
        self._set_sensitivity(3)
        delay(duration)
        self._set_sensitivity(0)

    @kernel
    def count(self):
        """Poll the RTIO input during all the previously programmed gate
        openings, and returns the number of registered events."""
        count = 0
        while syscall("rtio_get", self.channel,
                      self.i_previous_timestamp) >= 0:
            count += 1
        return count

    @kernel
    def timestamp(self):
        """Poll the RTIO input and returns an event timestamp, according to
        the gating.

        If the gate is permanently closed, returns a negative value.
        """
        return cycles_to_time(syscall("rtio_get", self.channel,
                                      self.i_previous_timestamp))
