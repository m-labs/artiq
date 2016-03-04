from artiq.language.core import syscall, kernel
from artiq.language.types import TBool, TInt32, TNone
from artiq.coredevice.exceptions import I2CError


@syscall
def i2c_init(busno: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall
def i2c_start(busno: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall
def i2c_stop(busno: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall
def i2c_write(busno: TInt32, b: TInt32) -> TBool:
    raise NotImplementedError("syscall not simulated")


@syscall
def i2c_read(busno: TInt32, ack: TBool) -> TInt32:
    raise NotImplementedError("syscall not simulated")


class PCA9548:
    def __init__(self, dmgr, busno=0, address=0x74):
        self.core = dmgr.get("core")
        self.busno = busno
        self.address = address

    @kernel
    def set(self, channel):
        i2c_init(self.busno)
        i2c_start(self.busno)
        try:
            if not i2c_write(self.busno, self.address):
                raise I2CError("PCA9548 failed to ack address")
            if not i2c_write(self.busno, 1 << channel):
                raise I2CError("PCA9548 failed to ack control word")
        finally:
            i2c_stop(self.busno)


class TCA6424A:
    def __init__(self, dmgr, busno=0, address=0x44):
        self.core = dmgr.get("core")
        self.busno = busno
        self.address = address

    @kernel
    def _write24(self, command, value):
        i2c_init(self.busno)
        i2c_start(self.busno)
        try:
            if not i2c_write(self.busno, self.address):
                raise I2CError("TCA6424A failed to ack address")
            if not i2c_write(self.busno, command):
                raise I2CError("TCA6424A failed to ack command")
            for i in range(3):
                if not i2c_write(self.busno, value >> 16):
                    raise I2CError("TCA6424A failed to ack command")
                value <<= 8
        finally:
            i2c_stop(self.busno)

    @kernel
    def set(self, outputs):
        self._write24(0x8c, 0)  # set all directions to output
        self._write24(0x84, output)  # set levels
