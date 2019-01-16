"""Driver for RTIO-enabled TTL edge counter.

Like for the TTL input PHYs, sensitivity can be configured over RTIO
(``gate_rising()``, etc.). In contrast to the former, however, the count is
accumulated in gateware, and only a single input event is generated at the end
of each gate period::

    with parallel:
        doppler_cool()
        self.pmt_counter.gate_rising(1 * ms)

    with parallel:
        readout()
        self.pmt_counter.gate_rising(100 * us)

    print("Doppler cooling counts:", self.pmt_counter.fetch_count())
    print("Readout counts:", self.pmt_counter.fetch_count())

For applications where the timestamps of the individual input events are not
required, this has two advantages over ``TTLInOut.count()`` beyond raw
throughput. First, it is easy to count events during multiple separate periods
without blocking to read back counts in between, as illustrated in the above
example. Secondly, as each count total only takes up a single input event, it
is much easier to acquire counts on several channels in parallel without
risking input FIFO overflows::

    # Using the TTLInOut driver, pmt_1 input events are only processed
    # after pmt_0 is done counting. To avoid RTIOOverflows, a round-robin
    # scheme would have to be implemented manually.

    with parallel:
        self.pmt_0.gate_rising(10 * ms)
        self.pmt_1.gate_rising(10 * ms)

    counts_0 = self.pmt_0.count(now_mu()) # blocks
    counts_1 = self.pmt_1.count(now_mu())

    #

    # Using gateware counters, only a single input event each is
    # generated, greatly reducing the load on the input FIFOs:

    with parallel:
        self.pmt_0_counter.gate_rising(10 * ms)
        self.pmt_1_counter.gate_rising(10 * ms)

    counts_0 = self.pmt_0_counter.fetch_count() # blocks
    counts_1 = self.pmt_1_counter.fetch_count()

See :mod:`artiq.gateware.rtio.phy.edge_counter` and
:meth:`artiq.gateware.eem.DIO.add_std` for the gateware components.
"""

from artiq.language.core import *
from artiq.language.types import *
from artiq.coredevice.rtio import (rtio_output, rtio_input_data,
                                   rtio_input_timestamped_data)
from numpy import int32, int64

CONFIG_COUNT_RISING = 0b0001
CONFIG_COUNT_FALLING = 0b0010
CONFIG_SEND_COUNT_EVENT = 0b0100
CONFIG_RESET_TO_ZERO = 0b1000


class CounterOverflow(Exception):
    """Raised when an edge counter value is read which indicates that the
    counter might have overflowed."""
    pass


class EdgeCounter:
    """RTIO TTL edge counter driver driver.

    Like for regular TTL inputs, timeline periods where the counter is
    sensitive to a chosen set of input transitions can be specified. Unlike the
    former, however, the specified edges do not create individual input events;
    rather, the total count can be requested as a single input event from the
    core (typically at the end of the gate window).

    :param channel: The RTIO channel of the gateware phy.
    :param gateware_width: The width of the gateware counter register, in
        bits. This is only used for overflow handling; to change the size,
        the gateware needs to be rebuilt.
    """

    kernel_invariants = {"core", "channel", "counter_max"}

    def __init__(self, dmgr, channel, gateware_width=31, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.counter_max = (1 << (gateware_width - 1)) - 1

    @kernel
    def gate_rising(self, duration):
        """Count rising edges for the given duration and request the total at
        the end.

        The counter is reset at the beginning of the gate period. Use
        :meth:`set_config` directly for more detailed control.

        :param duration: The duration for which the gate is to stay open.

        :return: The timestamp at the end of the gate period, in machine units.
        """
        return self.gate_rising_mu(self.core.seconds_to_mu(duration))

    @kernel
    def gate_falling(self, duration):
        """Count falling edges for the given duration and request the total at
        the end.

        The counter is reset at the beginning of the gate period. Use
        :meth:`set_config` directly for more detailed control.

        :param duration: The duration for which the gate is to stay open.

        :return: The timestamp at the end of the gate period, in machine units.
        """
        return self.gate_falling_mu(self.core.seconds_to_mu(duration))

    @kernel
    def gate_both(self, duration):
        """Count both rising and falling edges for the given duration, and
        request the total at the end.

        The counter is reset at the beginning of the gate period. Use
        :meth:`set_config` directly for more detailed control.

        :param duration: The duration for which the gate is to stay open.

        :return: The timestamp at the end of the gate period, in machine units.
        """
        return self.gate_both_mu(self.core.seconds_to_mu(duration))

    @kernel
    def gate_rising_mu(self, duration_mu):
        """See :meth:`gate_rising`."""
        return self._gate_mu(
            duration_mu, count_rising=True, count_falling=False)

    @kernel
    def gate_falling_mu(self, duration_mu):
        """See :meth:`gate_falling`."""
        return self._gate_mu(
            duration_mu, count_rising=False, count_falling=True)

    @kernel
    def gate_both_mu(self, duration_mu):
        """See :meth:`gate_both_mu`."""
        return self._gate_mu(
            duration_mu, count_rising=True, count_falling=True)

    @kernel
    def _gate_mu(self, duration_mu, count_rising, count_falling):
        self.set_config(
            count_rising=count_rising,
            count_falling=count_falling,
            send_count_event=False,
            reset_to_zero=True)
        delay_mu(duration_mu)
        self.set_config(
            count_rising=False,
            count_falling=False,
            send_count_event=True,
            reset_to_zero=False)
        return now_mu()

    @kernel
    def set_config(self, count_rising: TBool, count_falling: TBool,
                   send_count_event: TBool, reset_to_zero: TBool):
        """Emit an RTIO event at the current timeline position to set the
        gateware configuration.

        For most use cases, the `gate_*` wrappers will be more convenient.

        :param count_rising: Whether to count rising signal edges.
        :param count_falling: Whether to count falling signal edges.
        :param send_count_event: If `True`, an input event with the current
            counter value is generated on the next clock cycle (once).
        :param reset_to_zero: If `True`, the counter value is reset to zero on
            the next clock cycle (once).
        """
        config = int32(0)
        if count_rising:
            config |= CONFIG_COUNT_RISING
        if count_falling:
            config |= CONFIG_COUNT_FALLING
        if send_count_event:
            config |= CONFIG_SEND_COUNT_EVENT
        if reset_to_zero:
            config |= CONFIG_RESET_TO_ZERO
        rtio_output(self.channel << 8, config)

    @kernel
    def fetch_count(self) -> TInt32:
        """Wait for and return count total from previously requested input
        event.

        It is valid to trigger multiple gate periods without immediately
        reading back the count total; the results will be returned in order on
        subsequent fetch calls.

        This function blocks until a result becomes available.
        """
        count = rtio_input_data(self.channel)
        if count == self.counter_max:
            raise CounterOverflow(
                "Input edge counter overflow on RTIO channel {0}",
                int64(self.channel))
        return count

    @kernel
    def fetch_timestamped_count(
            self, timeout_mu=int64(-1)) -> TTuple([TInt64, TInt32]):
        """Wait for and return the timestamp and count total of a previously
        requested input event.

        It is valid to trigger multiple gate periods without immediately
        reading back the count total; the results will be returned in order on
        subsequent fetch calls.

        This function blocks until a result becomes available or the given
        timeout elapses.

        :return: A tuple of timestamp (-1 if timeout elapsed) and counter
            value. (The timestamp is that of the requested input event –
            typically the gate closing time – and not that of any input edges.)
        """
        timestamp, count = rtio_input_timestamped_data(timeout_mu,
                                                       self.channel)
        if count == self.counter_max:
            raise CounterOverflow(
                "Input edge counter overflow on RTIO channel {0}",
                int64(self.channel))
        return timestamp, count
