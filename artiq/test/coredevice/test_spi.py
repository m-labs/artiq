import unittest
from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.language.core import (kernel, delay_mu, delay)
from artiq.language.units import us
from artiq.coredevice import spi2 as spi


_SDCARD_SPI_CONFIG = (0*spi.SPI_OFFLINE | 0*spi.SPI_END |
                      0*spi.SPI_INPUT | 0*spi.SPI_CS_POLARITY |
                      0*spi.SPI_CLK_POLARITY | 0*spi.SPI_CLK_PHASE |
                      0*spi.SPI_LSB_FIRST | 0*spi.SPI_HALF_DUPLEX)


class CardTest(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("spi_mmc")

    @kernel
    def run(self):
        self.core.reset()
        
        freq = 1*MHz
        cs = 1

        # run a couple of clock cycles with miso high to wake up the card
        self.spi_mmc.set_config(_SDCARD_SPI_CONFIG, 32, freq, 0)
        for i in range(10):
            self.spi_mmc.write(0xffffffff)
        self.spi_mmc.set_config(_SDCARD_SPI_CONFIG | spi.SPI_END, 32, freq, 0)
        self.spi_mmc.write(0xffffffff)
        delay(200*us)

        self.spi_mmc.set_config(_SDCARD_SPI_CONFIG, 8, freq, cs)
        self.spi_mmc.write(0x40 << 24)  # CMD
        self.spi_mmc.set_config(_SDCARD_SPI_CONFIG, 32, freq, cs)
        self.spi_mmc.write(0x00000000)  # ARG
        self.spi_mmc.set_config(_SDCARD_SPI_CONFIG, 8, freq, cs)
        self.spi_mmc.write(0x95 << 24)  # CRC
        self.spi_mmc.set_config(_SDCARD_SPI_CONFIG | spi.SPI_INPUT, 8, freq, cs)
        idle = False
        response = 0
        for i in range(8):
            self.spi_mmc.write(0xff << 24)  # NCR
            response = self.spi_mmc.read()
            delay(100*us)
            if response == 0x01:
                idle = True
                break
        self.spi_mmc.set_config(_SDCARD_SPI_CONFIG | spi.SPI_END, 8, freq, cs)
        self.spi_mmc.write(0xff << 24)
        if not idle:
            print(response)
            raise ValueError("SD Card did not reply with IDLE")


class SDTest(ExperimentCase):
    def test(self):
        self.execute(CardTest)
