from migen import *

from artiq.gateware.rtio import rtlink
from artiq.gateware.grabber import deserializer_7series
from artiq.gateware.grabber.core import *


class Grabber(Module):
    def __init__(self, pins):
        self.config = rtlink.Interface(rtlink.OInterface(10))
        self.gate_data = rtlink.Interface(rtlink.OInterface(1),
                                          rtlink.IInterface(10))

        self.submodules.deserializer = deserializer_7series.Deserializer(pins)
        self.submodules.frequency_counter = FrequencyCounter()
        self.submodules.parser = Parser()
        self.comb += self.parser.cl.eq(self.deserializer.q)

    def get_csrs(self):
        return (
            self.deserializer.get_csrs() +
            self.frequency_counter.get_csrs() +
            self.parser.get_csrs())
