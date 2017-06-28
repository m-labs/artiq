from functools import reduce
from operator import and_

from migen import *
from migen.genlib.record import Record
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.resetsync import AsyncResetSynchronizer
from misoc.interconnect.csr import *

from artiq.gateware.rtio import cri, rtlink
from artiq.gateware.rtio.cdc import *


# CHOOSING A GUARD TIME
#
# The buffer must be transferred to the FIFO soon enough to account for:
#    * transfer of counter to sys domain: Tio + 2*Tsys + Tsys
#    * FIFO latency: Tsys + 2*Tio
#    * FIFO buffer latency: Tio
# Therefore we must choose:
#    guard_io_cycles > (4*Tio + 4*Tsys)/Tio
#
# We are writing to the FIFO from the buffer when the guard time has been
# reached. This can fill the FIFO and deassert the writable flag. A race
# condition occurs that causes problems if the deassertion happens between
# the CPU checking the writable flag (and reading 1) and writing a new event.
#
# When the FIFO is about to be full, it contains fifo_depth-1 events of
# strictly increasing timestamps.
#
# Thus the FIFO-filling event's timestamp must satisfy:
#    timestamp*Tio > (fifo_depth-1)*Tio + time
# We also have (guard time reached):
#    timestamp*Tio < time + guard_io_cycles*Tio
# [NB: time > counter.value_sys*Tio]
# Thus we must have:
#    guard_io_cycles > fifo_depth-1
#
# We can prevent overflows by choosing instead:
#    guard_io_cycles < fifo_depth-1

class _OutputManager(Module):
    def __init__(self, interface, counter, fifo_depth, guard_io_cycles):
        data_width = rtlink.get_data_width(interface)
        address_width = rtlink.get_address_width(interface)
        fine_ts_width = rtlink.get_fine_ts_width(interface)

        ev_layout = []
        if data_width:
            ev_layout.append(("data", data_width))
        if address_width:
            ev_layout.append(("address", address_width))
        ev_layout.append(("timestamp", counter.width + fine_ts_width))
        # ev must be valid 1 cycle before we to account for the latency in
        # generating replace, sequence_error and collision
        self.ev = Record(ev_layout)

        self.writable = Signal()
        self.we = Signal()  # maximum throughput 1/2

        self.underflow = Signal()  # valid 1 cycle after we, pulsed
        self.sequence_error = Signal()
        self.collision = Signal()
        self.busy = Signal()  # pulsed

        # # #

        # FIFO
        fifo = ClockDomainsRenamer({"write": "rsys", "read": "rio"})(
            AsyncFIFO(layout_len(ev_layout), fifo_depth))
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
            self.sync.rsys += replace.eq(self.ev.timestamp == buf.timestamp)
        # Detect sequence errors on coarse timestamps only
        # so that they are mutually exclusive with collision errors.
        self.sync.rsys += sequence_error.eq(self.ev.timestamp[fine_ts_width:] <
                                            buf.timestamp[fine_ts_width:])
        if interface.enable_replace:
            if address_width:
                different_addresses = self.ev.address != buf.address
            else:
                different_addresses = 0
            if fine_ts_width:
                self.sync.rsys += collision.eq(
                    (self.ev.timestamp[fine_ts_width:] == buf.timestamp[fine_ts_width:])
                    & ((self.ev.timestamp[:fine_ts_width] != buf.timestamp[:fine_ts_width])
                       |different_addresses))
            else:
                self.sync.rsys += collision.eq(
                    (self.ev.timestamp == buf.timestamp) & different_addresses)
        else:
            self.sync.rsys += collision.eq(
                self.ev.timestamp[fine_ts_width:] == buf.timestamp[fine_ts_width:])
        self.comb += [
            any_error.eq(sequence_error | collision),
            self.sequence_error.eq(self.we & sequence_error),
            self.collision.eq(self.we & collision)
        ]

        # Buffer read and FIFO write
        self.comb += fifo_in.eq(buf)
        in_guard_time = Signal()
        self.comb += in_guard_time.eq(
            buf.timestamp[fine_ts_width:]
                < counter.value_sys + guard_io_cycles)
        self.sync.rsys += If(in_guard_time, buf_pending.eq(0))
        self.comb += \
            If(buf_pending,
                If(in_guard_time,
                    If(buf_just_written,
                        self.underflow.eq(1)
                    ).Else(
                        fifo.we.eq(1)
                    )
                ),
                If(self.we & ~replace & ~any_error,
                   fifo.we.eq(1)
                )
            )

        # Buffer write
        # Must come after read to handle concurrent read+write properly
        self.sync.rsys += [
            buf_just_written.eq(0),
            If(self.we & ~any_error,
                buf_just_written.eq(1),
                buf_pending.eq(1),
                buf.eq(self.ev)
            )
        ]
        self.comb += self.writable.eq(fifo.writable)

        # Buffer output of FIFO to improve timing
        dout_stb = Signal()
        dout_ack = Signal()
        dout = Record(ev_layout)
        self.sync.rio += \
            If(fifo.re,
                dout_stb.eq(1),
                dout.eq(fifo_out)
            ).Elif(dout_ack,
                dout_stb.eq(0)
            )
        self.comb += fifo.re.eq(fifo.readable & (~dout_stb | dout_ack))

        # latency compensation
        if interface.delay:
            counter_rtio = Signal.like(counter.value_rtio)
            self.sync.rtio += counter_rtio.eq(counter.value_rtio -
                                              interface.delay + 1)
        else:
            counter_rtio = counter.value_rtio

        # FIFO read through buffer
        self.comb += [
            dout_ack.eq(
                dout.timestamp[fine_ts_width:] == counter_rtio),
            interface.stb.eq(dout_stb & dout_ack)
        ]

        busy_transfer = BlindTransfer()
        self.submodules += busy_transfer
        self.comb += [
            busy_transfer.i.eq(interface.stb & interface.busy),
            self.busy.eq(busy_transfer.o),
        ]

        if data_width:
            self.comb += interface.data.eq(dout.data)
        if address_width:
            self.comb += interface.address.eq(dout.address)
        if fine_ts_width:
            self.comb += interface.fine_ts.eq(dout.timestamp[:fine_ts_width])


class _InputManager(Module):
    def __init__(self, interface, counter, fifo_depth):
        data_width = rtlink.get_data_width(interface)
        fine_ts_width = rtlink.get_fine_ts_width(interface)

        ev_layout = []
        if data_width:
            ev_layout.append(("data", data_width))
        if interface.timestamped:
            ev_layout.append(("timestamp", counter.width + fine_ts_width))
        self.ev = Record(ev_layout)

        self.readable = Signal()
        self.re = Signal()

        self.overflow = Signal()  # pulsed

        # # #

        fifo = ClockDomainsRenamer({"read": "rsys", "write": "rio"})(
            AsyncFIFO(layout_len(ev_layout), fifo_depth))
        self.submodules += fifo
        fifo_in = Record(ev_layout)
        fifo_out = Record(ev_layout)
        self.comb += [
            fifo.din.eq(fifo_in.raw_bits()),
            fifo_out.raw_bits().eq(fifo.dout)
        ]

        # latency compensation
        if interface.delay:
            counter_rtio = Signal.like(counter.value_rtio)
            self.sync.rtio += counter_rtio.eq(counter.value_rtio -
                                              interface.delay + 1)
        else:
            counter_rtio = counter.value_rtio

        # FIFO write
        if data_width:
            self.comb += fifo_in.data.eq(interface.data)
        if interface.timestamped:
            if fine_ts_width:
                full_ts = Cat(interface.fine_ts, counter_rtio)
            else:
                full_ts = counter_rtio
            self.comb += fifo_in.timestamp.eq(full_ts)
        self.comb += fifo.we.eq(interface.stb)

        # FIFO read
        self.comb += [
            self.ev.eq(fifo_out),
            self.readable.eq(fifo.readable),
            fifo.re.eq(self.re)
        ]

        overflow_transfer = BlindTransfer()
        self.submodules += overflow_transfer
        self.comb += [
            overflow_transfer.i.eq(fifo.we & ~fifo.writable),
            self.overflow.eq(overflow_transfer.o),
        ]


class Channel:
    def __init__(self, interface, probes=None, overrides=None,
                 ofifo_depth=64, ififo_depth=64):
        if probes is None:
            probes = []
        if overrides is None:
            overrides = []

        self.interface = interface
        self.probes = probes
        self.overrides = overrides
        self.ofifo_depth = ofifo_depth
        self.ififo_depth = ififo_depth

    @classmethod
    def from_phy(cls, phy, **kwargs):
        probes = getattr(phy, "probes", [])
        overrides = getattr(phy, "overrides", [])
        return cls(phy.rtlink, probes, overrides, **kwargs)


class LogChannel:
    """A degenerate channel used to log messages into the analyzer."""
    def __init__(self):
        self.interface = rtlink.Interface(rtlink.OInterface(32))
        self.probes = []
        self.overrides = []


class _RelaxedAsyncResetSynchronizer(Module):
    def __init__(self, cd, async_reset):
        self.clock_domains.cd_rst = ClockDomain()
        rst_fan = Signal(reset_less=True)
        self.specials += AsyncResetSynchronizer(self.cd_rst, async_reset)
        self.comb += [
                self.cd_rst.clk.eq(cd.clk),
                cd.rst.eq(rst_fan),
        ]
        self.sync.rst += rst_fan.eq(self.cd_rst.rst)


class Core(Module, AutoCSR):
    def __init__(self, channels, fine_ts_width=None, guard_io_cycles=20):
        if fine_ts_width is None:
            fine_ts_width = max(rtlink.get_fine_ts_width(c.interface)
                                for c in channels)

        self.cri = cri.Interface()
        self.reset = CSR()
        self.reset_phy = CSR()
        self.async_error = CSR(2)

        # Clocking/Reset
        # Create rsys, rio and rio_phy domains based on sys and rtio
        # with reset controlled by CRI.
        #
        # The `rio` CD contains logic that is reset with `core.reset()`.
        # That's state that could unduly affect subsequent experiments,
        # i.e. input overflows caused by input gates left open, FIFO events far
        # in the future blocking the experiment, pending RTIO or
        # wishbone bus transactions, etc.
        # The `rio_phy` CD contains state that is maintained across
        # `core.reset()`, i.e. TTL output state, OE, DDS state.
        cmd_reset = Signal(reset=1)
        cmd_reset_phy = Signal(reset=1)
        self.sync += [
            cmd_reset.eq(self.reset.re),
            cmd_reset_phy.eq(self.reset_phy.re)
        ]
        cmd_reset.attr.add("no_retiming")
        cmd_reset_phy.attr.add("no_retiming")

        self.clock_domains.cd_rsys = ClockDomain()
        self.clock_domains.cd_rio = ClockDomain()
        self.clock_domains.cd_rio_phy = ClockDomain()
        self.comb += [
            self.cd_rsys.clk.eq(ClockSignal()),
            self.cd_rsys.rst.eq(cmd_reset),
            self.cd_rio.clk.eq(ClockSignal("rtio")),
            self.cd_rio_phy.clk.eq(ClockSignal("rtio"))
        ]
        self.submodules.rars_rio = _RelaxedAsyncResetSynchronizer(
                self.cd_rio, cmd_reset)
        self.submodules.rars_rio_phy = _RelaxedAsyncResetSynchronizer(
                self.cd_rio_phy, cmd_reset_phy)

        # Managers
        self.submodules.counter = RTIOCounter(len(self.cri.timestamp) - fine_ts_width)

        # Collision is not an asynchronous error with local RTIO, but
        # we treat it as such for consistency with DRTIO, where collisions
        # are reported by the satellites.
        o_underflow = Signal()
        o_sequence_error = Signal()
        o_collision = Signal()
        o_busy = Signal()
        self.sync.rsys += [
            If(self.cri.cmd == cri.commands["write"],
                o_underflow.eq(0),
                o_sequence_error.eq(0),
            )
        ]
        self.sync += [
            If(self.async_error.re,
                If(self.async_error.r[0], o_collision.eq(0)),
                If(self.async_error.r[1], o_busy.eq(0)),
            )
        ]

        o_statuses, i_statuses = [], []
        i_datas, i_timestamps = [], []
        i_ack = Signal()
        sel = self.cri.chan_sel[:16]
        for n, channel in enumerate(channels):
            if isinstance(channel, LogChannel):
                o_statuses.append(1)
                i_datas.append(0)
                i_timestamps.append(0)
                i_statuses.append(0)
                continue

            selected = Signal()
            self.comb += selected.eq(sel == n)

            o_manager = _OutputManager(channel.interface.o, self.counter,
                                       channel.ofifo_depth, guard_io_cycles)
            self.submodules += o_manager

            if hasattr(o_manager.ev, "data"):
                self.comb += o_manager.ev.data.eq(self.cri.o_data)
            if hasattr(o_manager.ev, "address"):
                self.comb += o_manager.ev.address.eq(self.cri.o_address)
            ts_shift = len(self.cri.timestamp) - len(o_manager.ev.timestamp)
            self.comb += o_manager.ev.timestamp.eq(self.cri.timestamp[ts_shift:])

            self.comb += o_manager.we.eq(selected & (self.cri.cmd == cri.commands["write"]))

            self.sync.rsys += [
                If(o_manager.underflow, o_underflow.eq(1)),
                If(o_manager.sequence_error, o_sequence_error.eq(1))
            ]
            self.sync += [
                If(o_manager.collision, o_collision.eq(1)),
                If(o_manager.busy, o_busy.eq(1))
            ]
            o_statuses.append(o_manager.writable)

            if channel.interface.i is not None:
                i_manager = _InputManager(channel.interface.i, self.counter,
                                          channel.ififo_depth)
                self.submodules += i_manager

                if hasattr(i_manager.ev, "data"):
                    i_datas.append(i_manager.ev.data)
                else:
                    i_datas.append(0)
                if channel.interface.i.timestamped:
                    ts_shift = (len(self.cri.i_timestamp) - len(i_manager.ev.timestamp))
                    i_timestamps.append(i_manager.ev.timestamp << ts_shift)
                else:
                    i_timestamps.append(0)

                overflow = Signal()
                self.sync.rsys += [
                    If(selected & i_ack,
                       overflow.eq(0)),
                    If(i_manager.overflow,
                       overflow.eq(1))
                ]
                self.comb += i_manager.re.eq(selected & i_ack & ~overflow)
                i_statuses.append(Cat(i_manager.readable & ~overflow, overflow))

            else:
                i_datas.append(0)
                i_timestamps.append(0)
                i_statuses.append(0)

        o_status_raw = Signal()
        self.comb += [
            o_status_raw.eq(Array(o_statuses)[sel]),
            self.cri.o_status.eq(Cat(
                ~o_status_raw, o_underflow, o_sequence_error)),
            self.async_error.w.eq(Cat(o_collision, o_busy))
        ]

        i_status_raw = Signal(2)
        self.comb += i_status_raw.eq(Array(i_statuses)[sel])
        input_timeout = Signal.like(self.cri.timestamp)
        input_pending = Signal()
        self.sync.rsys += [
            i_ack.eq(0),
            If(i_ack,
                self.cri.i_status.eq(Cat(~i_status_raw[0], i_status_raw[1], 0)),
                self.cri.i_data.eq(Array(i_datas)[sel]),
                self.cri.i_timestamp.eq(Array(i_timestamps)[sel]),
            ),
            If((self.cri.counter >= input_timeout) | (i_status_raw != 0),
                If(input_pending, i_ack.eq(1)),
                input_pending.eq(0)
            ),
            If(self.cri.cmd == cri.commands["read"],
                input_timeout.eq(self.cri.timestamp),
                input_pending.eq(1),
                self.cri.i_status.eq(0b100)
            )
        ]

        self.comb += self.cri.counter.eq(self.counter.value_sys << fine_ts_width)
