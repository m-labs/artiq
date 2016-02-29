from artiq.language.core import *
from artiq.language.types import *
from artiq.coredevice.rt2wb import *


SPI_DATA_ADDR, SPI_XFER_ADDR, SPI_CONFIG_ADDR = range(3)
(
    SPI_OFFLINE,
    SPI_ACTIVE,
    SPI_PENDING,
    SPI_CS_POLARITY,
    SPI_CLK_POLARITY,
    SPI_CLK_PHASE,
    SPI_LSB_FIRST,
    SPI_HALF_DUPLEX,
) = (1 << i for i in range(8))

SPI_RT2WB_READ = 1 << 2


class SPIMaster:
    """Core device Serial Peripheral Interface (SPI) bus master.

    :param ref_period: clock period of the SPI core.
    :param channel: channel number of the SPI bus to control.
    """
    def __init__(self, dmgr, ref_period, channel):
        self.core = dmgr.get("core")
        self.ref_period_mu = seconds_to_mu(ref_period, self.core)
        self.channel = channel
        self.write_div = 0
        self.read_div = 0
        # a full transfer takes prep_mu + xfer_mu
        self.prep_mu = 0
        # chained transfers can happen every xfer_mu
        self.xfer_mu = 0
        # The second transfer of a chain be written ref_period_mu
        # after the first. Read data is available every xfer_mu starting
        # a bit before prep_mu + xfer_mu.

    @portable
    def predict_xfer_mu(self, write_length, read_length):
        # this is only the intrinsic bit cycle duration
        return int(self.ref_period_mu*(
            write_length*self.write_div +
            read_length*self.read_div))

    @portable
    def predict_prep_mu(self, write_div):
        return int(self.ref_period_mu*(
            2 +  # intermediate transfers
            # one write_div for the wait+idle cycle
            self.write_div))

    @kernel
    def set_config(self, flags=0, write_div=6, read_div=6):
        self.write_div = write_div
        self.read_div = read_div
        self.prep_mu = self.predict_prep_mu(write_div)
        rt2wb_write(now_mu(), self.channel, SPI_CONFIG_ADDR, flags |
                    ((write_div - 2) << 8) | ((read_div - 2) << 20))
        delay_mu(self.ref_period_mu)

    @kernel
    def set_xfer(self, chip_select=0, write_length=0, read_length=0):
        self.xfer_mu = self.predict_xfer_mu(write_length, read_length)
        rt2wb_write(now_mu(), self.channel, SPI_XFER_ADDR,
                    chip_select | (write_length << 16) | (read_length << 24))
        delay_mu(self.ref_period_mu)

    @kernel
    def write(self, data):
        rt2wb_write(now_mu(), self.channel, SPI_DATA_ADDR, data)
        delay_mu(int(self.prep_mu + self.xfer_mu))

    @kernel
    def read_sync(self):
        r = rt2wb_read_sync(now_mu(), self.channel, SPI_DATA_ADDR |
                            SPI_RT2WB_READ, int(self.ref_period_mu))
        delay_mu(self.ref_period_mu)
        return r
