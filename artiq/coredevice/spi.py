from artiq.language.core import *
from artiq.language.types import *


@syscall
def spi_write(time_mu: TInt64, channel: TInt32, addr: TInt32, data: TInt32
              ) -> TNone:
    raise NotImplementedError("syscall not simulated")


@syscall
def spi_read(time_mu: TInt64, channel: TInt32, addr: TInt32) -> TInt32:
    raise NotImplementedError("syscall not simulated")


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


class SPIMaster:
    """Core device Serial Peripheral Interface (SPI) bus master.

    :param ref_period: clock period of the SPI core.
    :param channel: channel number of the SPI bus to control.
    """
    def __init__(self, dmgr, ref_period, channel):
        self.core = dmgr.get("core")
        self.ref_period_mu = int(seconds_to_mu(ref_period, self.core), 64)
        self.channel = channel
        self.write_div = 0
        self.read_div = 0
        # a full transfer takes prep_mu + xfer_mu
        self.prep_mu = int(0, 64)
        # chaned transfers can happen every xfer_mu
        self.xfer_mu = int(0, 64)
        # The second transfer of a chain be written ref_period_mu
        # after the first. Read data is available every xfer_mu starting
        # a bit before prep_mu + xfer_mu.

    @portable
    def predict_xfer_mu(self, write_length, read_length):
        # this is only the intrinsic bit cycle duration
        return self.ref_period_mu*(
            write_length*self.write_div +
            read_length*self.read_div)

    @portable
    def predict_prep_mu(self, write_div):
        return self.ref_period_mu*(
            2 +  # intermediate transfers
            # one write_div for the wait+idle cycle
            self.write_div)

    @kernel
    def set_config(self, flags=0, write_div=6, read_div=6):
        self.write_div = write_div
        self.read_div = read_div
        self.prep_mu = self.predict_prep_mu(write_div)
        spi_write(now_mu(), self.channel, SPI_CONFIG_ADDR, flags |
                  ((write_div - 2) << 8) | ((read_div - 2) << 20))
        delay_mu(self.ref_period_mu)

    @kernel
    def set_xfer(self, chip_select=0, write_length=0, read_length=0):
        self.xfer_mu = self.predict_xfer_mu(write_length, read_length)
        spi_write(now_mu(), self.channel, SPI_XFER_ADDR,
                  chip_select | (write_length << 16) | (read_length << 24))
        delay_mu(self.ref_period_mu)

    @kernel
    def write(self, data):
        spi_write(now_mu(), self.channel, SPI_DATA_ADDR, data)
        delay_mu(self.prep_mu + self.xfer_mu)

    @kernel
    def read(self):
        r = spi_read(now_mu(), self.channel, SPI_DATA_ADDR)
        delay_mu(self.ref_period_mu)
        return r
