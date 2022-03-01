from numpy import int32

from artiq.experiment import *
from artiq.coredevice.i2c import i2c_write_many, i2c_read_many, i2c_poll


port_mapping = {
    "EEM0": 7,
    "EEM1": 5,
    "EEM2": 4,
    "EEM3": 3,
    "EEM4": 2,
    "EEM5": 1,
    "EEM6": 0,
    "EEM7": 6,
    "EEM8": 12,
    "EEM9": 13,
    "EEM10": 15,
    "EEM11": 14,
    "SFP0": 8,
    "SFP1": 9,
    "SFP2": 10,
    "LOC0": 11,
}


class KasliEEPROM:
    def __init__(self, dmgr, port, busno=0,
            core_device="core", sw0_device="i2c_switch0", sw1_device="i2c_switch1"):
        self.core = dmgr.get(core_device)
        self.sw0 = dmgr.get(sw0_device)
        self.sw1 = dmgr.get(sw1_device)
        self.busno = busno
        self.port = port_mapping[port]
        self.address = 0xa0  # i2c 8 bit

    @kernel
    def select(self):
        mask = 1 << self.port
        self.sw0.select(mask)
        self.sw1.select(mask >> 8)

    @kernel
    def deselect(self):
        self.sw0.select(0)
        self.sw1.select(0)

    @kernel
    def write_i32(self, addr, value):
        self.select()
        try:
            data = [0]*4
            for i in range(4):
                data[i] = (value >> 24) & 0xff
                value <<= 8
            i2c_write_many(self.busno, self.address, addr, data)
            i2c_poll(self.busno, self.address)
        finally:
            self.deselect()

    @kernel
    def read_i32(self, addr):
        self.select()
        try:
            data = [0]*4
            i2c_read_many(self.busno, self.address, addr, data)
            value = int32(0)
            for i in range(4):
                value <<= 8
                value |= data[i]
        finally:
            self.deselect()
        return value
