from migen import *
from artiq.gateware.rtio import rtlink


class SimpleEdgeCounter(Module):
    """Counts rising/falling edges of an input signal.

    Control (sensitivity/zeroing) is done via a single RTIO output channel,
    which is is also used to request an input event to be emitted with the
    current counter value.

    :param input_state: The (scalar) input signal to detect edges of. This
        should already be in the rio_phy clock domain.
    :param counter_width: The width of the counter register, in bits. Defaults
        to 31 to match integers being signed in ARTIQ Python.
    """

    def __init__(self, input_state, counter_width=31):
        assert counter_width >= 2

        # RTIO interface:
        #  - output 0: 4 bits, <count_rising><count_falling><send_event><zero_counter>
        #  - input 0: 32 bits, accumulated edge count
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(4, enable_replace=False),
            rtlink.IInterface(counter_width))

        # # #

        current_count = Signal(counter_width)

        count_rising = Signal()
        count_falling = Signal()
        send_event_stb = Signal()
        zero_counter_stb = Signal()

        # Read configuration from RTIO output events.
        self.sync.rio += [
            If(self.rtlink.o.stb,
                count_rising.eq(self.rtlink.o.data[0]),
                count_falling.eq(self.rtlink.o.data[1]),
                send_event_stb.eq(self.rtlink.o.data[2]),
                zero_counter_stb.eq(self.rtlink.o.data[3])
            ).Else(
                send_event_stb.eq(0),
                zero_counter_stb.eq(0)
           )
        ]

        # Generate RTIO input event with current count if requested.
        event_data = Signal.like(current_count)
        self.comb += [
            self.rtlink.i.stb.eq(send_event_stb),
            self.rtlink.i.data.eq(event_data)
        ]

        # Keep previous input state for edge detection.
        input_state_d = Signal()
        self.sync.rio_phy += input_state_d.eq(input_state)

        # Count input edges, saturating at the maximum.
        new_count = Signal.like(current_count)
        self.comb += new_count.eq(
            current_count + Mux(current_count == 2**counter_width - 1,
                0,
                (count_rising & (input_state & ~input_state_d)) |
                (count_falling & (~input_state & input_state_d))
            )
        )

        self.sync.rio += [
            event_data.eq(new_count),
            current_count.eq(Mux(zero_counter_stb, 0, new_count))
        ]


if __name__ == '__main__':
    input = Signal(name="input")
    print(fhdl.verilog.convert(SimpleEdgeCounter(input)))
