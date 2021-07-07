import unittest
from artiq.experiment import *
from artiq.test.hardware_testbench import ExperimentCase
from artiq.language.core import kernel, delay
from artiq.language.units import us


class PhaserExperiment(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("phaser0")

    @kernel
    def run(self):
        self.core.reset()
        # The Phaser initialization performs a comprehensive test:
        # * Fastlink bringup
        # * Fastlink error counter
        # * Board identification
        # * Hardware identification
        # * SPI write, readback, timing
        # * Temperature readout
        # * DAC identification, IOTEST, alarm sweep, PLL configuration, FIFO
        #   alignmend
        # * DUC+Oscillator configuration, data end-to-end verification and
        #   readback
        # * Attenuator write and readback
        # * TRF bringup PLL locking
        self.phaser0.init()


class PhaserTest(ExperimentCase):
    def test(self):
        self.execute(PhaserExperiment)
