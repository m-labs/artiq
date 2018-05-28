from migen import *

from artiq.gateware.rtio import rtlink
from artiq.gateware.grabber import deserializer_7series


class Grabber(Module):
    def __init__(self, pins):
        self.config = rtlink.Interface(rtlink.OInterface(10))
        self.gate_data = rtlink.Interface(rtlink.OInterface(1),
                                          rtlink.IInterface(10))

        self.submodules.deserializer = deserializer_7series.Deserializer(pins)

    def get_csrs(self):
        return self.deserializer.get_csrs()
