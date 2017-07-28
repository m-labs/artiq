import unittest
from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.language.core import (kernel, delay_mu, delay)
from artiq.language.units import us
from artiq.coredevice import spi


_SDCARD_SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_CS_POLARITY |
                      0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
                      0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)

class CardTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("spi_mmc")

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        response = 0xff
        self.spi_mmc.set_config(_SDCARD_SPI_CONFIG, 500*kHz, 500*kHz)
        self.spi_mmc.set_xfer(0, 8, 0)

        for i in range(10):
            self.spi_mmc.write(0xffffffff)
            delay(-5*us)

        delay(100*us)

        self.spi_mmc.set_xfer(1, 8, 0)
        self.spi_mmc.write(0x40000000)
        delay(-5*us)
        self.spi_mmc.write(0x00000000)
        delay(-5*us)
        self.spi_mmc.write(0x00000000)
        delay(-5*us)
        self.spi_mmc.write(0x00000000)
        delay(-5*us)
        self.spi_mmc.write(0x00000000)
        delay(-5*us)
        self.spi_mmc.write(0x95000000)
        delay(-5*us)

        self.spi_mmc.set_xfer(1, 0, 24)
        self.spi_mmc.write(0xffffffff)
        response = self.spi_mmc.read_sync()

        sd_response = False
        for i in range(3):
            if ((response >> 8*i) & 0x0000ff) == 0x01:
                sd_response = True
                break
        self.set_dataset("sd_response", sd_response)


class SDTest(ExperimentCase):
    def test(self):
        self.execute(CardTest)
        self.assertTrue(self.dataset_mgr.get("sd_response"))
