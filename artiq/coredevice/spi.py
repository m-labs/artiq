from artiq.language.core import (kernel, seconds_to_mu, now_mu,
                                 delay_mu, int)
from artiq.language.units import MHz
from artiq.coredevice.rtio import rtio_output as rt2wb_output
from artiq.coredevice.rt2wb import rt2wb_input


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
        self.ref_period = ref_period
        self.ref_period_mu = int(seconds_to_mu(ref_period, self.core))
        self.channel = channel
        self.write_period_mu = int(0)
        self.read_period_mu = int(0)
        self.xfer_period_mu = int(0)
        # A full transfer takes write_period_mu + xfer_period_mu.
        # Chained transfers can happen every xfer_period_mu.
        # The second transfer of a chain can be written 2*ref_period_mu
        # after the first. Read data is available every xfer_period_mu starting
        # a bit after xfer_period_mu (depending on clk_phase).
        # To chain transfers together, new data must be written before
        # pending transfer's read data becomes available.

    @kernel
    def set_config(self, flags=0, write_freq=20*MHz, read_freq=20*MHz):
        write_div = round(1/(write_freq*self.ref_period))
        read_div = round(1/(read_freq*self.ref_period))
        self.set_config_mu(flags, write_div, read_div)

    @kernel
    def set_config_mu(self, flags=0, write_div=6, read_div=6):
        rt2wb_output(now_mu(), self.channel, SPI_CONFIG_ADDR, flags |
                     ((write_div - 2) << 16) | ((read_div - 2) << 24))
        self.write_period_mu = int(write_div*self.ref_period_mu)
        self.read_period_mu = int(read_div*self.ref_period_mu)
        delay_mu(3*self.ref_period_mu)

    @kernel
    def set_xfer(self, chip_select=0, write_length=0, read_length=0):
        rt2wb_output(now_mu(), self.channel, SPI_XFER_ADDR,
                     chip_select | (write_length << 16) | (read_length << 24))
        self.xfer_period_mu = int(write_length*self.write_period_mu +
                                  read_length*self.read_period_mu)
        delay_mu(3*self.ref_period_mu)

    @kernel
    def write(self, data):
        rt2wb_output(now_mu(), self.channel, SPI_DATA_ADDR, data)
        delay_mu(3*self.ref_period_mu)

    @kernel
    def read_async(self):
        # every read_async() must be matched by an input_async()
        rt2wb_output(now_mu(), self.channel, SPI_DATA_ADDR | SPI_RT2WB_READ, 0)
        delay_mu(3*self.ref_period_mu)

    @kernel
    def input_async(self):
        # matches the preeeding read_async()
        return rt2wb_input(self.channel)

    @kernel
    def read_sync(self):
        rt2wb_output(now_mu(), self.channel, SPI_DATA_ADDR | SPI_RT2WB_READ, 0)
        return rt2wb_input(self.channel)

    @kernel
    def _get_xfer_sync(self):
        rt2wb_output(now_mu(), self.channel, SPI_XFER_ADDR | SPI_RT2WB_READ, 0)
        return rt2wb_input(self.channel)

    @kernel
    def _get_config_sync(self):
        rt2wb_output(now_mu(), self.channel, SPI_CONFIG_ADDR | SPI_RT2WB_READ,
                     0)
        return rt2wb_input(self.channel)
