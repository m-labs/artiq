from migen import *

from artiq.gateware.drtio import link_layer, rt_packets, iot


class DRTIOSatellite(Module):
    def __init__(self, transceiver, channels, full_ts_width=63, fine_ts_width=3):
        self.submodules.link_layer = link_layer.LinkLayer(
            transceiver.encoder, transceiver.decoders)
        self.submodules.rt_packets = rt_packets.RTPacketSatellite(
            self.link_layer)
        self.submodules.iot = iot.IOT(
            self.rt_packets, channels, full_ts_width, fine_ts_width)


class DRTIOMaster(Module):
    def __init__(self):
        pass
