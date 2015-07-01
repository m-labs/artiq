from artiq.language.core import *
from artiq.language.db import *


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
    def set_o(self, o):
        syscall("ttl_set_o", now_mu(), self.channel, o)
        self.o_previous_timestamp = now_mu()

    @kernel
    def sync(self):
        """Busy-waits until all programmed level switches have been effected."""
        while syscall("rtio_get_counter") < self.o_previous_timestamp:
            pass

    @kernel
    def on(self):
        """Sets the output to a logic high state."""
        self.set_o(True)

    @kernel
    def off(self):
        """Sets the output to a logic low state."""
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
        """Busy-waits until all programmed level switches have been effected."""
        while syscall("rtio_get_counter") < self.o_previous_timestamp:
            pass

    @kernel
    def on(self):
        """Sets the output to a logic high state."""
        self.set_o(True)

    @kernel
    def off(self):
        """Sets the output to a logic low state."""
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
    def gate_both_mu(self, duration):
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
    def timestamp(self):
        """Poll the RTIO input and returns an event timestamp, according to
        the gating.

        If the gate is permanently closed, returns a negative value.
        """
        return syscall("ttl_get", self.channel, self.i_previous_timestamp)
