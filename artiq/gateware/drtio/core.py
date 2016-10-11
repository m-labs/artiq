from migen import *

from artiq.gateware.drtio import link_layer, rt_packets, iot


class DRTIOSatellite(Module):
    def __init__(self, transceiver, channels, fine_ts_width=3, full_ts_width=63):
        self.submodules.link_layer = link_layer.LinkLayer(
            transceiver.encoder, transceiver.decoders)
        self.submodules.rt_packets = rt_packets.RTPacketSatellite(
            self.link_layer)
        self.submodules.iot = iot.IOT(
            self.rt_packets, channels, fine_ts_width, full_ts_width)


class DRTIOMaster(Module):
    def __init__(self):
        pass
