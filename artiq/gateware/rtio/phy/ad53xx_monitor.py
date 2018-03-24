from migen import *

from artiq.coredevice.spi2 import SPI_CONFIG_ADDR, SPI_DATA_ADDR
from artiq.coredevice.ad53xx import AD53XX_CMD_DATA, ad53xx_cmd_write_ch


class AD53XXMonitor(Module):
    def __init__(self, spi_rtlink, ldac_rtlink=None, cs_no=0, cs_onehot=False, nchannels=32):
        self.probes = [Signal(16) for i in range(nchannels)]

        if ldac_rtlink is None:
            write_targets = self.probes
        else:
            write_targets = [Signal(16) for i in range(nchannels)]

            ldac_oif = ldac_rtlink.o
            if hasattr(ldac_oif, "address"):
                ttl_level_adr = ldac_oif.address == 0
            else:
                ttl_level_adr = 1
            self.sync.rio_phy += \
                If(ldac_oif.stb & ttl_level_adr & ~ldac_oif.data[0],
                    [probe.eq(write_target) for probe, write_target in zip(self.probes, write_targets)]
                )

        spi_oif = spi_rtlink.o

        selected = Signal()
        if cs_onehot:
            self.sync.rio_phy += [
                If(spi_oif.stb & (spi_oif.address == SPI_CONFIG_ADDR),
                    selected.eq(spi_oif.data[24 + cs_no])
                )
            ]
        else:
            self.sync.rio_phy += [
                If(spi_oif.stb & (spi_oif.address == SPI_CONFIG_ADDR),
                    selected.eq(spi_oif.data[24:] == cs_no)
                )
            ]

        writes = {
            ad53xx_cmd_write_ch(channel=i, value=0, op=AD53XX_CMD_DATA) >> 16:
                t.eq(spi_oif.data[8:24])
            for i, t in enumerate(write_targets)}
        self.sync.rio_phy += [
            If(spi_oif.stb & (spi_oif.address == SPI_DATA_ADDR),
                Case(spi_oif.data[24:], writes)
            )
        ]
