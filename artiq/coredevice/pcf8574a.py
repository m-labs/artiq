from artiq.experiment import kernel
from artiq.coredevice.i2c import (
    i2c_start, i2c_write, i2c_read, i2c_stop, I2CError)


class PCF8574A:
    """Driver for the PCF8574 I2C remote 8-bit I/O expander.

    I2C transactions not real-time, and are performed by the CPU without
    involving RTIO.
    """
    def __init__(self, dmgr, busno=0, address=0x7c, core_device="core"):
        self.core = dmgr.get(core_device)
        self.busno = busno
        self.address = address

    @kernel
    def set(self, data):
        """Drive data on the quasi-bidirectional pins.

        :param data: Pin data. High bits are weakly driven high
            (and thus inputs), low bits are strongly driven low.
        """
        i2c_start(self.busno)
        try:
            if not i2c_write(self.busno, self.address):
                raise I2CError("PCF8574A failed to ack address")
            if not i2c_write(self.busno, data):
                raise I2CError("PCF8574A failed to ack data")
        finally:
            i2c_stop(self.busno)

    @kernel
    def get(self):
        """Retrieve quasi-bidirectional pin input data.

        :return: Pin data
        """
        i2c_start(self.busno)
        ret = 0
        try:
            if not i2c_write(self.busno, self.address | 1):
                raise I2CError("PCF8574A failed to ack address")
            ret = i2c_read(self.busno, False)
        finally:
            i2c_stop(self.busno)
        return ret
