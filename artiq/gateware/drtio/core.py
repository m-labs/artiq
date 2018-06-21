from types import SimpleNamespace

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.cdc import PulseSynchronizer
from misoc.interconnect.csr import *

from artiq.gateware.rtio.sed.core import *
from artiq.gateware.rtio.input_collector import *
from artiq.gateware.drtio import (link_layer, aux_controller,
                                  rt_packet_satellite, rt_errors_satellite,
                                  rt_packet_master, rt_controller_master)
from artiq.gateware.drtio.rx_synchronizer import GenericRXSynchronizer


class ChannelInterface:
    def __init__(self, encoder, decoders):
        self.rx_ready = Signal()
        self.encoder = encoder
        self.decoders = decoders


class TransceiverInterface(AutoCSR):
    def __init__(self, channel_interfaces):
        self.stable_clkin = CSRStorage()
        self.clock_domains.cd_rtio = ClockDomain()
        for i in range(len(channel_interfaces)):
            name = "rtio_rx" + str(i)
            setattr(self.clock_domains, "cd_"+name, ClockDomain(name=name))
        self.channels = channel_interfaces


class DRTIOSatellite(Module):
    def __init__(self, chanif, channels, rx_synchronizer=None, fine_ts_width=3,
                 lane_count=8, fifo_depth=128):
        self.reset = CSRStorage(reset=1)
        self.reset_phy = CSRStorage(reset=1)
        self.tsc_loaded = CSR()

        self.clock_domains.cd_rio = ClockDomain()
        self.clock_domains.cd_rio_phy = ClockDomain()
        self.comb += [
            self.cd_rio.clk.eq(ClockSignal("rtio")),
            self.cd_rio_phy.clk.eq(ClockSignal("rtio"))
        ]
        reset = Signal()
        reset_phy = Signal()
        reset.attr.add("no_retiming")
        reset_phy.attr.add("no_retiming")
        self.sync += [
            reset.eq(self.reset.storage),
            reset_phy.eq(self.reset_phy.storage)
        ]
        self.specials += [
            AsyncResetSynchronizer(self.cd_rio, reset),
            AsyncResetSynchronizer(self.cd_rio_phy, reset_phy)
        ]

        self.submodules.link_layer = link_layer.LinkLayer(
            chanif.encoder, chanif.decoders)
        self.comb += self.link_layer.rx_ready.eq(chanif.rx_ready)

        if rx_synchronizer is None:
            rx_synchronizer = GenericRXSynchronizer()
            self.submodules += rx_synchronizer

        link_layer_sync = SimpleNamespace(
            tx_aux_frame=self.link_layer.tx_aux_frame,
            tx_aux_data=self.link_layer.tx_aux_data,
            tx_aux_ack=self.link_layer.tx_aux_ack,
            tx_rt_frame=self.link_layer.tx_rt_frame,
            tx_rt_data=self.link_layer.tx_rt_data,

            rx_aux_stb=rx_synchronizer.resync(self.link_layer.rx_aux_stb),
            rx_aux_frame=rx_synchronizer.resync(self.link_layer.rx_aux_frame),
            rx_aux_frame_perm=rx_synchronizer.resync(self.link_layer.rx_aux_frame_perm),
            rx_aux_data=rx_synchronizer.resync(self.link_layer.rx_aux_data),
            rx_rt_frame=rx_synchronizer.resync(self.link_layer.rx_rt_frame),
            rx_rt_frame_perm=rx_synchronizer.resync(self.link_layer.rx_rt_frame_perm),
            rx_rt_data=rx_synchronizer.resync(self.link_layer.rx_rt_data)
        )
        self.submodules.link_stats = link_layer.LinkLayerStats(link_layer_sync, "rtio")
        self.submodules.rt_packet = ClockDomainsRenamer("rtio")(
            rt_packet_satellite.RTPacketSatellite(link_layer_sync))
        self.comb += self.rt_packet.reset.eq(self.cd_rio.rst)

        coarse_ts = Signal(64 - fine_ts_width)
        self.sync.rtio += \
            If(self.rt_packet.tsc_load,
                coarse_ts.eq(self.rt_packet.tsc_load_value)
            ).Else(
                coarse_ts.eq(coarse_ts + 1)
            )
        self.comb += self.rt_packet.cri.counter.eq(coarse_ts << fine_ts_width)
        self.coarse_ts = coarse_ts

        ps_tsc_load = PulseSynchronizer("rtio", "sys")
        self.submodules += ps_tsc_load
        self.comb += ps_tsc_load.i.eq(self.rt_packet.tsc_load)
        self.sync += [
            If(self.tsc_loaded.re, self.tsc_loaded.w.eq(0)),
            If(ps_tsc_load.o, self.tsc_loaded.w.eq(1))
        ]

        self.submodules.outputs = ClockDomainsRenamer("rio")(
            SED(channels, fine_ts_width, "sync",
                lane_count=lane_count, fifo_depth=fifo_depth,
                enable_spread=False, report_buffer_space=True,
                interface=self.rt_packet.cri))
        self.comb += self.outputs.coarse_timestamp.eq(coarse_ts)
        self.sync.rtio += self.outputs.minimum_coarse_timestamp.eq(coarse_ts + 16)

        self.submodules.inputs = ClockDomainsRenamer("rio")(
            InputCollector(channels, fine_ts_width, "sync",
                           interface=self.rt_packet.cri))
        self.comb += self.inputs.coarse_timestamp.eq(coarse_ts)

        self.submodules.rt_errors = rt_errors_satellite.RTErrorsSatellite(
            self.rt_packet, self.outputs)

        self.submodules.aux_controller = aux_controller.AuxController(
            self.link_layer)

    def get_csrs(self):
        return ([self.reset, self.reset_phy, self.tsc_loaded] +
                self.link_layer.get_csrs() + self.link_stats.get_csrs() +
                self.rt_errors.get_csrs() + self.aux_controller.get_csrs())


class DRTIOMaster(Module):
    def __init__(self, chanif, channel_count=1024, fine_ts_width=3):
        self.submodules.link_layer = link_layer.LinkLayer(
            chanif.encoder, chanif.decoders)
        self.comb += self.link_layer.rx_ready.eq(chanif.rx_ready)

        self.submodules.link_stats = link_layer.LinkLayerStats(self.link_layer, "rtio_rx")
        self.submodules.rt_packet = rt_packet_master.RTPacketMaster(self.link_layer)
        self.submodules.rt_controller = rt_controller_master.RTController(
            self.rt_packet, channel_count, fine_ts_width)
        self.submodules.rt_manager = rt_controller_master.RTManager(self.rt_packet)
        self.cri = self.rt_controller.cri

        self.submodules.aux_controller = aux_controller.AuxController(
            self.link_layer)

    def get_csrs(self):
        return (self.link_layer.get_csrs() +
                self.link_stats.get_csrs() +
                self.rt_controller.get_csrs() +
                self.rt_manager.get_csrs() +
                self.aux_controller.get_csrs())
