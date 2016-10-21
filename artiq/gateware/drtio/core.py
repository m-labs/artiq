from types import SimpleNamespace

from migen import *

from artiq.gateware.drtio import link_layer, rt_packets, iot


class DRTIOSatellite(Module):
    def __init__(self, transceiver, rx_synchronizer, channels, fine_ts_width=3, full_ts_width=63):
        self.submodules.link_layer = link_layer.LinkLayer(
            transceiver.encoder, transceiver.decoders)
        self.comb += [
            transceiver.rx_reset.eq(self.link_layer.rx_reset),
            self.link_layer.rx_ready.eq(transceiver.rx_ready)
        ]

        link_layer_sync = SimpleNamespace(
            tx_aux_frame=self.link_layer.tx_aux_frame,
            tx_aux_data=self.link_layer.tx_aux_data,
            tx_aux_ack=self.link_layer.tx_aux_ack,
            tx_rt_frame=self.link_layer.tx_rt_frame,
            tx_rt_data=self.link_layer.tx_rt_data,

            rx_aux_stb=rx_synchronizer.resync(self.link_layer.rx_aux_stb),
            rx_aux_frame=rx_synchronizer.resync(self.link_layer.rx_aux_frame),
            rx_aux_data=rx_synchronizer.resync(self.link_layer.rx_aux_data),
            rx_rt_frame=rx_synchronizer.resync(self.link_layer.rx_rt_frame),
            rx_rt_data=rx_synchronizer.resync(self.link_layer.rx_rt_data)
        )
        self.submodules.rt_packets = ClockDomainsRenamer("rtio")(
            rt_packets.RTPacketSatellite(link_layer_sync))

        self.submodules.iot = ClockDomainsRenamer("rtio")(
            iot.IOT(self.rt_packets, channels, fine_ts_width, full_ts_width))

        # TODO: remote resets
        self.clock_domains.cd_rio = ClockDomain()
        self.clock_domains.cd_rio_phy = ClockDomain()
        self.comb += [
            self.cd_rio.clk.eq(ClockSignal("rtio")),
            self.cd_rio.rst.eq(ResetSignal("rtio")),
            self.cd_rio_phy.clk.eq(ClockSignal("rtio")),
            self.cd_rio_phy.rst.eq(ResetSignal("rtio")),
        ]


class DRTIOMaster(Module):
    def __init__(self, transceiver):
        self.submodules.link_layer = link_layer.LinkLayer(
            transceiver.encoder, transceiver.decoders)
        self.comb += [
            transceiver.rx_reset.eq(self.link_layer.rx_reset),
            self.link_layer.rx_ready.eq(transceiver.rx_ready)
        ]
        self.submodules.rt_packets = rt_packets.RTPacketMaster(self.link_layer)
