from artiq.language.core import *
from artiq.language.db import *


class LLRTIOOut(AutoDB):
    """Low-level RTIO output driver.

    Allows setting RTIO outputs at arbitrary times, without time unit
    conversion.

    This is meant to be used mostly in drivers; consider using
    ``RTIOOut`` instead.
    """
    class DBKeys:
        core = Device()
        channel = Argument()

    def build(self):
        self._set_oe()

    @kernel
    def _set_oe(self):
        syscall("rtio_set_oe", time_to_cycles(now()), self.channel, True)

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
        self.set_o(t, 1)

    @kernel
    def off(self, t):
        """Turns the RTIO channel off.

        :param t: timestamp in RTIO cycles (64-bit integer).
        """
        self.set_o(t, 0)


class RTIOOut(AutoDB):
    """RTIO output driver.

    Configures the corresponding RTIO channel as output on the core device and
    provides functions to set its level.

    This driver supports zero-length transition suppression. For example, if
    two pulses are emitted back-to-back with no delay between them, they will
    be merged into a single pulse with a duration equal to the sum of the
    durations of the original pulses.

    :param core: core device
    :param channel: channel number
    """
    class DBKeys:
        core = Device()
        channel = Argument()

    def build(self):
        self.previous_timestamp = int64(0)  # in RTIO cycles
        self._set_oe()

    @kernel
    def _set_oe(self):
        syscall("rtio_set_oe", time_to_cycles(now()), self.channel, True)

    @kernel
    def _set_o(self, value):
        syscall("rtio_set_o", time_to_cycles(now()), self.channel, value)
        self.previous_timestamp = time_to_cycles(now())

    @kernel
    def sync(self):
        """Busy-waits until all programmed level switches have been effected.

        This function is useful to synchronize CPU-controlled devices (such as
        the AD9858 DDS bus) with related RTIO controls (such as RF switches at
        the output of the DDS).
        """
        while syscall("rtio_get_counter") < self.previous_timestamp:
            pass

    @kernel
    def on(self):
        """Sets the output to a logic high state."""
        self._set_o(1)

    @kernel
    def off(self):
        """Sets the output to a logic low state."""
        self._set_o(0)

    @kernel
    def pulse(self, duration):
        """Pulses the output high for the specified duration."""
        self.on()
        delay(duration)
        self.off()


class RTIOIn(AutoDB):
    """RTIO input driver.

    Configures the corresponding RTIO channel as input on the core device and
    provides functions to analyze the incoming signal, with real-time gating
    to prevent overflows.

    :param core: core device
    :param channel: channel number
    """
    class DBKeys:
        core = Device()
        channel = Argument()

    def build(self):
        self.previous_timestamp = int64(0)  # in RTIO cycles
        self._set_oe()

    @kernel
    def _set_oe(self):
        syscall("rtio_set_oe", time_to_cycles(now()), self.channel, False)

    @kernel
    def _set_sensitivity(self, value):
        syscall("rtio_set_sensitivity", time_to_cycles(now()), self.channel, value)
        self.previous_timestamp = time_to_cycles(now())

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
        while syscall("rtio_get", self.channel, self.previous_timestamp) >= 0:
            count += 1
        return count

    @kernel
    def timestamp(self):
        """Poll the RTIO input and returns an event timestamp, according to
        the gating.

        If the gate is permanently closed, returns a negative value.
        """
        return cycles_to_time(syscall("rtio_get", self.channel,
                                      self.previous_timestamp))
