from functools import reduce
from operator import and_

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import BlindTransfer
from misoc.interconnect.csr import *

from artiq.gateware.rtio import cri
from artiq.gateware.rtio import rtlink
from artiq.gateware.rtio.channel import *
from artiq.gateware.rtio.sed.core import *
from artiq.gateware.rtio.input_collector import *


class Core(Module, AutoCSR):
    def __init__(self, tsc, channels, lane_count=8, fifo_depth=128):
        self.cri = cri.Interface()
        self.reset = CSR()
        self.reset_phy = CSR()
        self.async_error = CSR(3)
        self.collision_channel = CSRStatus(16)
        self.busy_channel = CSRStatus(16)
        self.sequence_error_channel = CSRStatus(16)

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
        chan_fine_ts_width = max(max(rtlink.get_fine_ts_width(channel.interface.o)
                                     for channel in channels),
                                 max(rtlink.get_fine_ts_width(channel.interface.i)
                                     for channel in channels))
        assert tsc.glbl_fine_ts_width >= chan_fine_ts_width

        # Outputs/Inputs
        quash_channels = [n for n, c in enumerate(channels) if isinstance(c, LogChannel)]

        outputs = SED(channels, tsc.glbl_fine_ts_width, "async",
            quash_channels=quash_channels,
            lane_count=lane_count, fifo_depth=fifo_depth,
            interface=self.cri)
        self.submodules += outputs
        self.comb += outputs.coarse_timestamp.eq(tsc.coarse_ts)
        self.sync += outputs.minimum_coarse_timestamp.eq(tsc.coarse_ts_sys + 16)

        inputs = InputCollector(tsc, channels, "async",
            quash_channels=quash_channels,
            interface=self.cri)
        self.submodules += inputs

        # Asychronous output errors
        o_collision_sync = BlindTransfer("rio", "rsys", data_width=16)
        o_busy_sync = BlindTransfer("rio", "rsys", data_width=16)
        self.submodules += o_collision_sync, o_busy_sync
        o_collision = Signal()
        o_busy = Signal()
        o_sequence_error = Signal()
        self.sync += [
            If(self.async_error.re,
                If(self.async_error.r[0], o_collision.eq(0)),
                If(self.async_error.r[1], o_busy.eq(0)),
                If(self.async_error.r[2], o_sequence_error.eq(0)),
            ),
            If(o_collision_sync.o, 
                o_collision.eq(1),
                If(~o_collision,
                    self.collision_channel.status.eq(o_collision_sync.data_o)
                )
            ),
            If(o_busy_sync.o, 
                o_busy.eq(1),
                If(~o_busy,
                    self.busy_channel.status.eq(o_busy_sync.data_o)
                )
            ),
            If(outputs.sequence_error, 
                o_sequence_error.eq(1),
                If(~o_sequence_error,
                    self.sequence_error_channel.status.eq(outputs.sequence_error_channel)
                )
            )
        ]
        self.comb += self.async_error.w.eq(Cat(o_collision, o_busy, o_sequence_error))

        self.comb += [
            o_collision_sync.i.eq(outputs.collision),
            o_collision_sync.data_i.eq(outputs.collision_channel),
            o_busy_sync.i.eq(outputs.busy),
            o_busy_sync.data_i.eq(outputs.busy_channel)
        ]
