"""Real-time I/O scheduler for satellites"""

from migen import *
from migen.genlib.fifo import SyncFIFOBuffered
from migen.genlib.record import *

from artiq.gateware.rtio import rtlink


class IOS(Module):
    def __init__(self, rt_packet, channels, max_fine_ts_width, full_ts_width):
        self.write_underflow = Signal()
        self.write_overflow = Signal()
        self.write_sequence_error = Signal()
        self.collision = Signal()
        self.busy = Signal()

        self.rt_packet = rt_packet
        self.max_fine_ts_width = max_fine_ts_width

        self.tsc = Signal(full_ts_width - max_fine_ts_width)
        self.sync.rtio += \
            If(rt_packet.tsc_load,
                self.tsc.eq(rt_packet.tsc_load_value)
            ).Else(
                self.tsc.eq(self.tsc + 1)
            )
        self.comb += rt_packet.tsc_input.eq(self.tsc)

        self.sync.rio += [
            self.write_underflow.eq(0),
            self.write_overflow.eq(0),
            self.collision.eq(0),
            self.busy.eq(0)
        ]
        for n, channel in enumerate(channels):
            self.add_output(n, channel)
            self.add_input(n, channel)

    def add_output(self, n, channel):
        rt_packet = self.rt_packet
        max_fine_ts_width = self.max_fine_ts_width

        interface = channel.interface.o
        data_width = rtlink.get_data_width(interface)
        address_width = rtlink.get_address_width(interface)
        fine_ts_width = rtlink.get_fine_ts_width(interface)
        assert fine_ts_width <= max_fine_ts_width

        we = Signal()
        self.comb += we.eq(rt_packet.write_stb
                           & (rt_packet.write_channel == n))
        write_timestamp = rt_packet.write_timestamp[max_fine_ts_width-fine_ts_width:]
        write_timestamp_coarse = rt_packet.write_timestamp[max_fine_ts_width:]
        write_timestamp_fine = rt_packet.write_timestamp[max_fine_ts_width-fine_ts_width:max_fine_ts_width]

        # latency compensation
        if interface.delay:
            tsc_comp = Signal.like(self.tsc)
            self.sync.rtio += tsc_comp.eq(self.tsc - interface.delay + 1)
        else:
            tsc_comp = self.tsc

        # FIFO
        ev_layout = []
        if data_width:
            ev_layout.append(("data", data_width))
        if address_width:
            ev_layout.append(("address", address_width))
        ev_layout.append(("timestamp", len(self.tsc) + fine_ts_width))

        fifo = ClockDomainsRenamer("rio")(
            SyncFIFOBuffered(layout_len(ev_layout), channel.ofifo_depth))
        self.submodules += fifo
        fifo_in = Record(ev_layout)
        fifo_out = Record(ev_layout)
        self.comb += [
            fifo.din.eq(fifo_in.raw_bits()),
            fifo_out.raw_bits().eq(fifo.dout)
        ]

        # Buffer
        buf_pending = Signal()
        buf = Record(ev_layout)
        buf_just_written = Signal()

        # Special cases
        replace = Signal()
        sequence_error = Signal()
        collision = Signal()
        any_error = Signal()
        if interface.enable_replace:
            # Note: replace may be asserted at the same time as collision
            # when addresses are different. In that case, it is a collision.
            self.sync.rio += replace.eq(write_timestamp == buf.timestamp)
        # Detect sequence errors on coarse timestamps only
        # so that they are mutually exclusive with collision errors.
        self.sync.rio += sequence_error.eq(write_timestamp_coarse < buf.timestamp[fine_ts_width:])
        if interface.enable_replace:
            if address_width:
                different_addresses = rt_packet.write_address != buf.address
            else:
                different_addresses = 0
            if fine_ts_width:
                self.sync.rio += collision.eq(
                    (write_timestamp_coarse == buf.timestamp[fine_ts_width:])
                    & ((write_timestamp_fine != buf.timestamp[:fine_ts_width])
                       |different_addresses))
            else:
                self.sync.rio += collision.eq(
                    (write_timestamp == buf.timestamp) & different_addresses)
        else:
            self.sync.rio += collision.eq(
                write_timestamp_coarse == buf.timestamp[fine_ts_width:])
        self.comb += any_error.eq(sequence_error | collision)
        self.sync.rio += [
            If(we & sequence_error, self.write_sequence_error.eq(1)),
            If(we & collision, self.collision.eq(1))
        ]

        # Buffer read and FIFO write
        self.comb += fifo_in.eq(buf)
        in_guard_time = Signal()
        self.comb += in_guard_time.eq(
            buf.timestamp[fine_ts_width:] < tsc_comp + 4)
        self.sync.rio += If(in_guard_time, buf_pending.eq(0))
        report_underflow = Signal()
        self.comb += \
            If(buf_pending,
                If(in_guard_time,
                    If(buf_just_written,
                        report_underflow.eq(1)
                    ).Else(
                        fifo.we.eq(1)
                    )
                ),
                If(we & ~replace & ~any_error,
                   fifo.we.eq(1)
                )
            )
        self.sync.rio += If(report_underflow, self.write_underflow.eq(1))

        # Buffer write
        # Must come after read to handle concurrent read+write properly
        self.sync.rio += [
            buf_just_written.eq(0),
            If(we & ~any_error,
                buf_just_written.eq(1),
                buf_pending.eq(1),
                buf.timestamp.eq(write_timestamp),
                buf.data.eq(rt_packet.write_data) if data_width else [],
                buf.address.eq(rt_packet.write_address) if address_width else [],
            ),
            If(we & ~fifo.writable, self.write_overflow.eq(1))
        ]

        # FIFO level
        self.sync.rio += \
            If(rt_packet.fifo_space_update &
               (rt_packet.fifo_space_channel == n),
                rt_packet.fifo_space.eq(channel.ofifo_depth - fifo.level))

        # FIFO read
        self.sync.rio += [
            fifo.re.eq(0),
            interface.stb.eq(0),
            If(fifo.readable &
               (fifo_out.timestamp[fine_ts_width:] == tsc_comp),
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

        self.sync.rio += If(interface.stb & interface.busy, self.busy.eq(1))

    def add_input(self, n, channel):
        rt_packet = self.rt_packet

        interface = channel.interface.i
        if interface is None:
            return
        data_width = rtlink.get_data_width(interface)
        fine_ts_width = rtlink.get_fine_ts_width(interface)

        selected = Signal()
        self.comb += selected.eq(rt_packet.read_channel == n)

        # latency compensation
        if interface.delay:
            tsc_comp = Signal.like(self.tsc)
            self.sync.rtio += tsc_comp.eq(self.tsc - interface.delay + 1)
        else:
            tsc_comp = self.tsc

        # FIFO
        ev_layout = []
        if data_width:
            ev_layout.append(("data", data_width))
        if interface.timestamped:
            ev_layout.append(("timestamp", len(self.tsc) + fine_ts_width))

        fifo = ClockDomainsRenamer("rio")(
            SyncFIFOBuffered(layout_len(ev_layout), channel.ififo_depth))
        self.submodules += fifo
        fifo_in = Record(ev_layout)
        fifo_out = Record(ev_layout)
        self.comb += [
            fifo.din.eq(fifo_in.raw_bits()),
            fifo_out.raw_bits().eq(fifo.dout)
        ]

        # FIFO write
        if data_width:
            self.comb += fifo_in.data.eq(interface.data)
        if interface.timestamped:
            if fine_ts_width:
                full_ts = Cat(interface.fine_ts, tsc_comp)
            else:
                full_ts = tsc_comp
            self.comb += fifo_in.timestamp.eq(full_ts)
        self.comb += fifo.we.eq(interface.stb)

        overflow = Signal()
        self.comb += If(selected, rt_packet.read_overflow.eq(overflow))
        self.sync.rio += [
            If(selected & rt_packet.read_overflow_ack, overflow.eq(0)),
            If(fifo.we & ~fifo.writable, overflow.eq(1))
        ]

        # FIFO read
        if data_width:
            self.comb += If(selected, rt_packet.read_data.eq(fifo_out.data))
        if interface.timestamped:
            self.comb += If(selected, rt_packet.read_timestamp.eq(fifo_out.timestamp))
        self.comb += [
            If(selected,
                rt_packet.read_readable.eq(fifo.readable),
                fifo.re.eq(rt_packet.read_consume)
            )
        ]
