from functools import reduce
from operator import and_

from migen import *
from migen.genlib.record import Record
from migen.genlib.fifo import AsyncFIFO
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import PulseSynchronizer
from misoc.interconnect.csr import *

from artiq.gateware.rtio import cri
from artiq.gateware.rtio import rtlink
from artiq.gateware.rtio.channel import *
from artiq.gateware.rtio.cdc import *
from artiq.gateware.rtio.sed.core import *


class _InputManager(Module):
    def __init__(self, interface, coarse_ts, fifo_depth):
        data_width = rtlink.get_data_width(interface)
        fine_ts_width = rtlink.get_fine_ts_width(interface)

        ev_layout = []
        if data_width:
            ev_layout.append(("data", data_width))
        if interface.timestamped:
            ev_layout.append(("timestamp", len(coarse_ts) + fine_ts_width))
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
            counter_rtio = Signal.like(coarse_ts, reset_less=True)
            self.sync.rtio += counter_rtio.eq(coarse_ts -
                                              (interface.delay + 1))
        else:
            counter_rtio = coarse_ts

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


class _Inputs(Module):
    def __init__(self, interface, coarse_ts, channels):
        self.cri = interface

        # Inputs
        i_statuses = []
        i_datas, i_timestamps = [], []
        i_ack = Signal()
        sel = self.cri.chan_sel[:16]
        for n, channel in enumerate(channels):
            if isinstance(channel, LogChannel):
                i_datas.append(0)
                i_timestamps.append(0)
                i_statuses.append(0)
                continue

            if channel.interface.i is not None:
                selected = Signal()
                self.comb += selected.eq(sel == n)

                i_manager = _InputManager(channel.interface.i, coarse_ts,
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


class Core(Module, AutoCSR):
    def __init__(self, channels, lane_count=8, fifo_depth=128):
        self.cri = cri.Interface()
        self.reset = CSR()
        self.reset_phy = CSR()
        self.async_error = CSR(2)

        # Clocking/Reset
        # Create rsys, rio and rio_phy domains based on sys and rtio
        # with reset controlled by CSR.
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
        self.specials += AsyncResetSynchronizer(self.cd_rio, cmd_reset)
        self.specials += AsyncResetSynchronizer(self.cd_rio_phy, cmd_reset_phy)

        # TSC
        fine_ts_width = max(max(rtlink.get_fine_ts_width(channel.interface.o)
                                for channel in channels),
                            max(rtlink.get_fine_ts_width(channel.interface.i)
                                for channel in channels))
        coarse_ts = Signal(64-fine_ts_width)
        self.sync.rtio += coarse_ts.eq(coarse_ts + 1)
        coarse_ts_cdc = GrayCodeTransfer(len(coarse_ts))
        self.submodules += coarse_ts_cdc
        self.comb += [
            coarse_ts_cdc.i.eq(coarse_ts),
            self.cri.counter.eq(coarse_ts_cdc.o << fine_ts_width)
        ]

        # Asychronous output errors
        o_collision_sync = PulseSynchronizer("rtio", "rsys")
        o_busy_sync = PulseSynchronizer("rtio", "rsys")
        self.submodules += o_collision_sync, o_busy_sync
        o_collision = Signal()
        o_busy = Signal()
        self.sync += [
            If(self.async_error.re,
                If(self.async_error.r[0], o_collision.eq(0)),
                If(self.async_error.r[1], o_busy.eq(0)),
            ),
            If(o_collision_sync.o, o_collision.eq(1)),
            If(o_busy_sync.o, o_busy.eq(1))
        ]
        self.comb += self.async_error.w.eq(Cat(o_collision, o_busy))

        # Inputs
        inputs = _Inputs(self.cri, coarse_ts, channels)
        self.submodules += inputs

        # Outputs
        outputs = SED(channels, "async",
            quash_channels=[n for n, c in enumerate(channels) if isinstance(c, LogChannel)],
            interface=self.cri)
        self.submodules += outputs
        self.comb += outputs.coarse_timestamp.eq(coarse_ts)
        self.sync += outputs.minimum_coarse_timestamp.eq(coarse_ts + 16)
        self.comb += [
            o_collision_sync.i.eq(outputs.collision),
            o_busy_sync.i.eq(outputs.busy)
        ]
