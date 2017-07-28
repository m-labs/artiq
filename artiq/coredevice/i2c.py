"""
Non-realtime drivers for I2C chips on the core device.
"""


from artiq.language.core import syscall, kernel
from artiq.language.types import TBool, TInt32, TNone
from artiq.coredevice.exceptions import I2CError


@syscall(flags={"nounwind", "nowrite"})
def i2c_start(busno: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def i2c_restart(busno: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def i2c_stop(busno: TInt32) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def i2c_write(busno: TInt32, b: TInt32) -> TBool:
    raise NotImplementedError("syscall not simulated")


@syscall(flags={"nounwind", "nowrite"})
def i2c_read(busno: TInt32, ack: TBool) -> TInt32:
    raise NotImplementedError("syscall not simulated")


class PCA9548:
    """Driver for the PCA9548 I2C bus switch.

    I2C transactions not real-time, and are performed by the CPU without
    involving RTIO.

    On the KC705, this chip is used for selecting the I2C buses on the two FMC
    connectors. HPC=1, LPC=2.
    """
    def __init__(self, dmgr, busno=0, address=0xe8, core_device="core"):
        self.core = dmgr.get(core_device)
        self.busno = busno
        self.address = address

    @kernel
    def set(self, channel):
        """Select one channel.

        Selecting multiple channels at the same time is not supported by this
        driver.

        :param channel: channel number (0-7)
        """
        i2c_start(self.busno)
        try:
            if not i2c_write(self.busno, self.address):
                raise I2CError("PCA9548 failed to ack address")
            if not i2c_write(self.busno, 1 << channel):
                raise I2CError("PCA9548 failed to ack control word")
        finally:
            i2c_stop(self.busno)

    @kernel
    def readback(self):
        i2c_start(self.busno)
        r = 0
        try:
            if not i2c_write(self.busno, self.address | 1):
                raise I2CError("PCA9548 failed to ack address")
            r = i2c_read(self.busno, False)
        finally:
            i2c_stop(self.busno)
        return r


class TCA6424A:
    """Driver for the TCA6424A I2C I/O expander.

    I2C transactions not real-time, and are performed by the CPU without
    involving RTIO.

    On the NIST QC2 hardware, this chip is used for switching the directions
    of TTL buffers."""
    def __init__(self, dmgr, busno=0, address=0x44, core_device="core"):
        self.core = dmgr.get(core_device)
        self.busno = busno
        self.address = address

    @kernel
    def _write24(self, command, value):
        i2c_start(self.busno)
        try:
            if not i2c_write(self.busno, self.address):
                raise I2CError("TCA6424A failed to ack address")
            if not i2c_write(self.busno, command):
                raise I2CError("TCA6424A failed to ack command")
            for i in range(3):
                if not i2c_write(self.busno, value >> 16):
                    raise I2CError("TCA6424A failed to ack data")
                value <<= 8
        finally:
            i2c_stop(self.busno)

    @kernel
    def set(self, outputs):
        """Drive all pins of the chip to the levels given by the
        specified 24-bit word.

        On the QC2 hardware, the LSB of the word determines the direction of
        TTL0 (on a given FMC card) and the MSB that of TTL23.

        A bit set to 1 means the TTL is an output.
        """
        outputs_le = (
            ((outputs & 0xff0000) >> 16) |
            (outputs & 0x00ff00) |
            (outputs & 0x0000ff) << 16)

        self._write24(0x8c, 0)  # set all directions to output
        self._write24(0x84, outputs_le)  # set levels
