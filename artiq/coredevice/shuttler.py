import numpy

from artiq.language.core import *
from artiq.language.types import *
from artiq.coredevice.rtio import rtio_output, rtio_input_data


class Config:
    kernel_invariants = {
        "core", "channel", "target_base", "target_read",
        "target_gain", "target_offset", "target_clr"
    }

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_base   = channel << 8
        self.target_read   = 1 << 6
        self.target_gain   = 0 * (1 << 4)
        self.target_offset = 1 * (1 << 4)
        self.target_clr    = 1 * (1 << 5)

    @kernel
    def set_clr(self, clr):
        rtio_output(self.target_base | self.target_clr, clr)
    
    @kernel
    def set_gain(self, channel, gain):
        rtio_output(self.target_base | self.target_gain | channel, gain)
    
    @kernel
    def get_gain(self, channel):
        rtio_output(self.target_base | self.target_gain |
            self.target_read | channel, 0)
        return rtio_input_data(self.channel)
    
    @kernel
    def set_offset(self, channel, offset):
        rtio_output(self.target_base | self.target_offset | channel, offset)

    @kernel
    def get_offset(self, channel):
        rtio_output(self.target_base | self.target_offset |
            self.target_read | channel, 0)
        return rtio_input_data(self.channel)


class Volt:
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def set_waveform(self, a0: TInt32, a1: TInt32, a2: TInt64, a3: TInt64):
        pdq_words = [
            a0,
            a1,
            a1 >> 16,
            a2 & 0xFFFF,
            (a2 >> 16) & 0xFFFF,
            (a2 >> 32) & 0xFFFF,
            a3 & 0xFFFF,
            (a3 >> 16) & 0xFFFF,
            (a3 >> 32) & 0xFFFF,
        ]

        for i in range(len(pdq_words)):
            rtio_output(self.target_o | i, pdq_words[i])
            delay_mu(int64(self.core.ref_multiplier))


class Dds:
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def set_waveform(self, b0: TInt32, b1: TInt32, b2: TInt64, b3: TInt64,
            c0: TInt32, c1: TInt32, c2: TInt32):
        pdq_words = [
            b0,
            b1,
            b1 >> 16,
            b2 & 0xFFFF,
            (b2 >> 16) & 0xFFFF,
            (b2 >> 32) & 0xFFFF,
            b3 & 0xFFFF,
            (b3 >> 16) & 0xFFFF,
            (b3 >> 32) & 0xFFFF,
            c0,
            c1,
            c1 >> 16,
            c2,
            c2 >> 16,
        ]

        for i in range(len(pdq_words)):
            rtio_output(self.target_o | i, pdq_words[i])
            delay_mu(int64(self.core.ref_multiplier))


class Trigger:
    kernel_invariants = {"core", "channel", "target_o"}

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @kernel
    def trigger(self, trig_out):
        rtio_output(self.target_o, trig_out)
