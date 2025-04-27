from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.i2c import I2CSwitch, i2c_write_many, i2c_read_many, i2c_poll


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


@compile
class KasliEEPROM:
    core: KernelInvariant[Core]
    sw0: KernelInvariant[I2CSwitch]
    sw1: KernelInvariant[I2CSwitch]
    busno: KernelInvariant[int32]
    port: KernelInvariant[int32]
    address: KernelInvariant[int32]

    def __init__(self, dmgr, port, address=0xa0, busno=0,
                 core_device="core", sw0_device="i2c_switch0", sw1_device="i2c_switch1"):
        self.core = dmgr.get(core_device)
        self.sw0 = dmgr.get(sw0_device)
        self.sw1 = dmgr.get(sw1_device)
        self.busno = busno
        self.port = port_mapping[port]
        self.address = address  # i2c 8 bit

    @kernel
    def select(self):
        mask = 1 << self.port
        if self.port < 8:
            self.sw0.set(self.port)
            self.sw1.unset()
        else:
            self.sw0.unset()
            self.sw1.set(self.port - 8)

    @kernel
    def deselect(self):
        self.sw0.unset()
        self.sw1.unset()

    @kernel
    def write_i32(self, addr: int32, value: int32):
        self.select()
        try:
            data = [0 for _ in range(4)]
            for i in range(4):
                data[i] = (value >> 24) & 0xff
                value <<= 8
            i2c_write_many(self.busno, self.address, addr, data)
            i2c_poll(self.busno, self.address)
        finally:
            self.deselect()

    @kernel
    def read_i32(self, addr: int32) -> int32:
        self.select()
        value = int32(0)
        try:
            data = [0 for _ in range(4)]
            i2c_read_many(self.busno, self.address, addr, data)
            for i in range(4):
                value <<= 8
                value |= data[i]
        finally:
            self.deselect()
        return value
