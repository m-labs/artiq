from artiq.language.core import *


class LLRTIOOut(AutoContext):
    """Low-level RTIO output driver.

    Allows setting RTIO outputs at arbitrary times, without time unit
    conversion.

    This is meant to be used mostly in drivers; consider using
    ``RTIOOut`` instead.

    """
    parameters = "channel"

    def build(self):
        self._set_oe()

    @kernel
    def _set_oe(self):
        syscall("rtio_oe", self.channel, True)

    @kernel
    def set_value(self, t, value):
        """Sets the value of the RTIO channel.

        :param t: timestamp in RTIO cycles (64-bit integer).
        :param value: value to set at the output.

        """
        syscall("rtio_set", t, self.channel, value)

    @kernel
    def on(self, t):
        """Turns the RTIO channel on.

        :param t: timestamp in RTIO cycles (64-bit integer).

        """
        self.set_value(t, 1)

    @kernel
    def off(self, t):
        """Turns the RTIO channel off.

        :param t: timestamp in RTIO cycles (64-bit integer).

        """
        self.set_value(t, 0)


class _RTIOBase(AutoContext):
    parameters = "channel"

    def build(self):
        self.previous_timestamp = int64(0)  # in RTIO cycles

    @kernel
    def _set_oe(self, oe):
        syscall("rtio_oe", self.channel, oe)

    @kernel
    def _set_value(self, value):
        syscall("rtio_set", time_to_cycles(now()), self.channel, value)
        self.previous_timestamp = time_to_cycles(now())


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
        self._set_oe(True)

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
        self._set_oe(False)

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
    def pileup_count(self):
        """Returns the number of pileup events (a system clock cycle with too
        many input transitions) since the last call to this function for this
        channel (or since the last RTIO reset).

        """
        return syscall("rtio_pileup_count", self.channel)

    @kernel
    def count(self):
        """Poll the RTIO input during all the previously programmed gate
        openings, and returns the number of registered events.

        """
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
