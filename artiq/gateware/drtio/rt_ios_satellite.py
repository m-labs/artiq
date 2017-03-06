"""Real-time I/O scheduler for satellites"""

from migen import *
from migen.genlib.fifo import SyncFIFOBuffered
from migen.genlib.record import *

from artiq.gateware.rtio import rtlink


class IOS(Module):
    def __init__(self, rt_packet, channels, max_fine_ts_width, full_ts_width):
        tsc = Signal(full_ts_width - max_fine_ts_width)
        self.sync.rtio += \
            If(rt_packet.tsc_load,
                tsc.eq(rt_packet.tsc_load_value)
            ).Else(
                tsc.eq(tsc + 1)
            )
        self.comb += rt_packet.tsc_input.eq(tsc)

        for n, channel in enumerate(channels):
            interface = channel.interface.o
            data_width = rtlink.get_data_width(interface)
            address_width = rtlink.get_address_width(interface)
            fine_ts_width = rtlink.get_fine_ts_width(interface)
            assert fine_ts_width <= max_fine_ts_width

            # FIFO
            ev_layout = []
            if data_width:
                ev_layout.append(("data", data_width))
            if address_width:
                ev_layout.append(("address", address_width))
            ev_layout.append(("timestamp", len(tsc) + fine_ts_width))

            fifo = ClockDomainsRenamer("rio")(
                SyncFIFOBuffered(layout_len(ev_layout), channel.ofifo_depth))
            self.submodules += fifo
            fifo_in = Record(ev_layout)
            fifo_out = Record(ev_layout)
            self.comb += [
                fifo.din.eq(fifo_in.raw_bits()),
                fifo_out.raw_bits().eq(fifo.dout)
            ]

            # FIFO level
            self.sync.rio += \
                If(rt_packet.fifo_space_update &
                   (rt_packet.fifo_space_channel == n),
                    rt_packet.fifo_space.eq(channel.ofifo_depth - fifo.level))

            # FIFO write
            self.comb += fifo.we.eq(rt_packet.write_stb
                                    & (rt_packet.write_channel == n))
            self.sync.rio += [
                If(rt_packet.write_overflow_ack,
                    rt_packet.write_overflow.eq(0)),
                If(rt_packet.write_underflow_ack,
                    rt_packet.write_underflow.eq(0)),
                If(fifo.we,
                    If(~fifo.writable, rt_packet.write_overflow.eq(1)),
                    If(rt_packet.write_timestamp[max_fine_ts_width:] < (tsc + 4),
                        rt_packet.write_underflow.eq(1)
                    )
                )
            ]
            if data_width:
                self.comb += fifo_in.data.eq(rt_packet.write_data)
            if address_width:
                self.comb += fifo_in.address.eq(rt_packet.write_address)
            self.comb += fifo_in.timestamp.eq(
                rt_packet.write_timestamp[max_fine_ts_width-fine_ts_width:])

            # FIFO read
            self.sync.rio += [
                fifo.re.eq(0),
                interface.stb.eq(0),
                If(fifo.readable &
                   (fifo_out.timestamp[fine_ts_width:] == tsc),
                    fifo.re.eq(1),
                    interface.stb.eq(1)
                )
            ]
            if data_width:
                self.sync.rio += interface.data.eq(fifo_out.data)
            if address_width:
                self.sync.rio += interface.address.eq(fifo_out.address)
            if fine_ts_width:
                self.sync.rio += interface.fine_ts.eq(fifo_out.timestamp[:fine_ts_width])
