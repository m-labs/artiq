from migen import *

from artiq.coredevice.spi2 import SPI_CONFIG_ADDR
from artiq.coredevice.urukul import CS_DDS_MULTI, CS_CFG, CFG_IO_UPDATE


class AD9910_AD9912MonitorGeneric(Module):
    def __init__(self, spi_phy, io_update_phy):
        self.spi_phy = spi_phy
        self.io_update_phy = io_update_phy

        self.current_address = Signal.like(self.spi_phy.rtlink.o.address)
        self.current_data = Signal.like(self.spi_phy.rtlink.o.data)
        self.cs = Signal(8)
        self.length = Signal(8)
        self.flags = Signal(8)

        self.sync.rio += If(self.spi_phy.rtlink.o.stb, [
            self.current_address.eq(self.spi_phy.rtlink.o.address),
            self.current_data.eq(self.spi_phy.rtlink.o.data),
            If(self.current_address == SPI_CONFIG_ADDR, [
                self.cs.eq(self.current_data[24:]),
                self.length.eq(self.current_data[8:16] + 1),
                self.flags.eq(self.current_data[0:8])
            ])
        ])

    def selected(self, c):
        return (self.cs == CS_DDS_MULTI) | (self.cs == c)

    def is_io_update(self):
        # shifted 8 bits left for 32-bit bus
        dest_cfg_reg_and_io_update_bit_set = (self.cs == CS_CFG) & self.current_data[8 + CFG_IO_UPDATE]
        if self.io_update_phy is not None:
            io_update_strobe_set_and_high = self.io_update_phy.rtlink.o.stb & self.io_update_phy.rtlink.o.data
            return io_update_strobe_set_and_high | dest_cfg_reg_and_io_update_bit_set
        return dest_cfg_reg_and_io_update_bit_set


