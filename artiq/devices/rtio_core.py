from artiq.language.core import *
from artiq.devices.runtime_exceptions import RTIOSequenceError


class _RTIOBase(AutoContext):
    parameters = "channel"

    def build(self):
        self.previous_timestamp = int64(0)  # in RTIO cycles
        self.previous_value = 0

    kernel_attr = "previous_timestamp previous_value"

    @kernel
    def _set_oe(self, oe):
        syscall("rtio_oe", self.channel, oe)

    @kernel
    def _set_value(self, value):
        if time_to_cycles(now()) < self.previous_timestamp:
            raise RTIOSequenceError
        if self.previous_value != value:
            if self.previous_timestamp == time_to_cycles(now()):
                syscall("rtio_replace", time_to_cycles(now()),
                        self.channel, value)
            else:
                syscall("rtio_set", time_to_cycles(now()),
                        self.channel, value)
            self.previous_timestamp = time_to_cycles(now())
            self.previous_value = value


class RTIOOut(_RTIOBase):
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
    def build(self):
        _RTIOBase.build(self)
        self._set_oe(1)

    @kernel
    def sync(self):
        """Busy-waits until all programmed level switches have been effected.

        This function is useful to synchronize CPU-controlled devices (such as
        the AD9858 DDS bus) with related RTIO controls (such as RF switches at
        the output of the DDS).

        """
        syscall("rtio_sync", self.channel)

    @kernel
    def on(self):
        """Sets the output to a logic high state.

        """
        self._set_value(1)

    @kernel
    def off(self):
        """Sets the output to a logic low state.

        """
        self._set_value(0)

    @kernel
    def pulse(self, duration):
        """Pulses the output high for the specified duration.

        """
        self.on()
        delay(duration)
        self.off()


class RTIOIn(_RTIOBase):
    """RTIO input driver.

    Configures the corresponding RTIO channel as input on the core device and
    provides functions to analyze the incoming signal, with real-time gating
    to prevent overflows.

    :param core: core device
    :param channel: channel number

    """
    def build(self):
        _RTIOBase.build(self)
        self._set_oe(0)

    @kernel
    def gate_rising(self, duration):
        """Register rising edge events for the specified duration.

        """
        self._set_value(1)
        delay(duration)
        self._set_value(0)

    @kernel
    def gate_falling(self, duration):
        """Register falling edge events for the specified duration.

        """
        self._set_value(2)
        delay(duration)
        self._set_value(0)

    @kernel
    def gate_both(self, duration):
        """Register both rising and falling edge events for the specified
        duration.

        """
        self._set_value(3)
        delay(duration)
        self._set_value(0)

    @kernel
    def count(self):
        """Poll the RTIO input during all the previously programmed gate
        openings, and returns the number of registered events.

        """
        count = 0
        while syscall("rtio_get", self.channel) >= 0:
            count += 1
        return count

    @kernel
    def timestamp(self):
        """Poll the RTIO input and returns an event timestamp, according to
        the gating.

        If the gate is permanently closed, returns a negative value.

        """
        return cycles_to_time(syscall("rtio_get", self.channel))
