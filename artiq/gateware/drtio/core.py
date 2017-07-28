from types import SimpleNamespace

from migen import *
from migen.genlib.cdc import ElasticBuffer

from artiq.gateware.drtio import (link_layer, aux_controller,
                                  rt_packet_satellite, rt_ios_satellite,
                                  rt_errors_satellite,
                                  rt_packet_master, rt_controller_master) 


class ChannelInterface:
    def __init__(self, encoder, decoders):
        self.rx_ready = Signal()
        self.encoder = encoder
        self.decoders = decoders


class TransceiverInterface:
    def __init__(self, channel_interfaces):
        self.clock_domains.cd_rtio = ClockDomain()
        for i in range(len(channel_interfaces)):
            name = "rtio_rx" + str(i)
            setattr(self.clock_domains, "cd_"+name, ClockDomain(name=name))
        self.channels = channel_interfaces


class GenericRXSynchronizer(Module):
    """Simple RX synchronizer based on the portable Migen elastic buffer.

    Introduces timing non-determinism in the satellite -> master path,
    (and in the echo_request/echo_reply RTT) but useful for testing.
    """
    def __init__(self):
        self.signals = []

    def resync(self, signal):
        synchronized = Signal.like(signal, related=signal)
        self.signals.append((signal, synchronized))
        return synchronized

    def do_finalize(self):
        eb = ElasticBuffer(sum(len(s[0]) for s in self.signals), 4, "rtio_rx", "rtio")
        self.submodules += eb
        self.comb += [
            eb.din.eq(Cat(*[s[0] for s in self.signals])),
            Cat(*[s[1] for s in self.signals]).eq(eb.dout)
        ]


class DRTIOSatellite(Module):
    def __init__(self, chanif, channels, rx_synchronizer=None, fine_ts_width=3, full_ts_width=63):
        if rx_synchronizer is None:
            rx_synchronizer = GenericRXSynchronizer()
            self.submodules += rx_synchronizer

        self.submodules.link_layer = link_layer.LinkLayer(
            chanif.encoder, chanif.decoders)
        self.comb += self.link_layer.rx_ready.eq(chanif.rx_ready)

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

        self.submodules.ios = rt_ios_satellite.IOS(
            self.rt_packet, channels, fine_ts_width, full_ts_width)

        self.submodules.rt_errors = rt_errors_satellite.RTErrorsSatellite(
            self.rt_packet, self.ios)

        self.clock_domains.cd_rio = ClockDomain()
        self.clock_domains.cd_rio_phy = ClockDomain()
        self.comb += [
            self.cd_rio.clk.eq(ClockSignal("rtio")),
            self.cd_rio.rst.eq(self.rt_packet.reset),
            self.cd_rio_phy.clk.eq(ClockSignal("rtio")),
            self.cd_rio_phy.rst.eq(self.rt_packet.reset_phy),
        ]

        self.submodules.aux_controller = aux_controller.AuxController(
            self.link_layer)

    def get_csrs(self):
        return (self.link_layer.get_csrs() + self.link_stats.get_csrs() +
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
