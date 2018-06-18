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


@kernel
def i2c_poll(busno, busaddr):
    """Poll I2C device at address.

    :param busno: I2C bus number
    :param busaddr: 8 bit I2C device address (LSB=0)
    :returns: True if the poll was ACKed
    """
    i2c_start(busno)
    ack = i2c_write(busno, busaddr)
    i2c_stop(busno)
    return ack


@kernel
def i2c_write_byte(busno, busaddr, data, ack=True):
    """Write one byte to a device.

    :param busno: I2C bus number
    :param busaddr: 8 bit I2C device address (LSB=0)
    :param data: Data byte to be written
    :param nack: Allow NACK
    """
    i2c_start(busno)
    try:
        if not i2c_write(busno, busaddr):
            raise I2CError("failed to ack bus address")
        if not i2c_write(busno, data) and ack:
            raise I2CError("failed to ack write data")
    finally:
        i2c_stop(busno)


@kernel
def i2c_read_byte(busno, busaddr):
    """Read one byte from a device.

    :param busno: I2C bus number
    :param busaddr: 8 bit I2C device address (LSB=0)
    :returns: Byte read
    """
    i2c_start(busno)
    data = 0
    try:
        if not i2c_write(busno, busaddr | 1):
            raise I2CError("failed to ack bus read address")
        data = i2c_read(busno, ack=False)
    finally:
        i2c_stop(busno)
    return data


@kernel
def i2c_write_many(busno, busaddr, addr, data, ack_last=True):
    """Transfer multiple bytes to a device.

    :param busno: I2c bus number
    :param busaddr: 8 bit I2C device address (LSB=0)
    :param addr: 8 bit data address
    :param data: Data bytes to be written
    :param ack_last: Expect I2C ACK of the last byte written. If `False`,
        the last byte may be NACKed (e.g. EEPROM full page writes).
    """
    n = len(data)
    i2c_start(busno)
    try:
        if not i2c_write(busno, busaddr):
            raise I2CError("failed to ack bus address")
        if not i2c_write(busno, addr):
            raise I2CError("failed to ack data address")
        for i in range(n):
            if not i2c_write(busno, data[i]) and (
                    i < n - 1 or ack_last):
                raise I2CError("failed to ack write data")
    finally:
        i2c_stop(busno)


@kernel
def i2c_read_many(busno, busaddr, addr, data):
    """Transfer multiple bytes from a device.

    :param busno: I2c bus number
    :param busaddr: 8 bit I2C device address (LSB=0)
    :param addr: 8 bit data address
    :param data: List of integers to be filled with the data read.
        One entry ber byte.
    """
    m = len(data)
    i2c_start(busno)
    try:
        if not i2c_write(busno, busaddr):
            raise I2CError("failed to ack bus address")
        if not i2c_write(busno, addr):
            raise I2CError("failed to ack data address")
        i2c_restart(busno)
        if not i2c_write(busno, busaddr | 1):
            raise I2CError("failed to ack bus read address")
        for i in range(m):
            data[i] = i2c_read(busno, ack=i < m - 1)
    finally:
        i2c_stop(busno)


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
    def select(self, mask):
        """Enable/disable channels.

        :param mask: Bit mask of enabled channels
        """
        i2c_write_byte(self.busno, self.address, mask)

    @kernel
    def set(self, channel):
        """Enable one channel.

        :param channel: channel number (0-7)
        """
        self.select(1 << channel)

    @kernel
    def readback(self):
        return i2c_read_byte(self.busno, self.address)


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
    def _write24(self, addr, value):
        i2c_write_many(self.busno, self.address, addr,
                       [value >> 16, value >> 8, value])

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
