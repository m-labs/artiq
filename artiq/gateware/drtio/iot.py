from migen import *
from migen.genlib.fifo import SyncFIFOBuffered

from artiq.gateware.rtio import rtlink


class IOT(Module):
    def __init__(self, rt_packets, channels, full_ts_width, fine_ts_width):
        pass
