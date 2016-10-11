import time

from artiq.coredevice.ad9154_reg import *
from artiq.experiment import *


class Test(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ad9154")

    def run(self):
        self.stpl()

    def stpl(self):
        # short transport layer test
        for i, data in enumerate([0x0123, 0x4567, 0x89ab, 0xcdef]):
            # select dac
            self.ad9154.dac_write(AD9154_SHORT_TPL_TEST_0,
                AD9154_SHORT_TPL_TEST_EN_SET(0) |
                AD9154_SHORT_TPL_TEST_RESET_SET(0) |
                AD9154_SHORT_TPL_DAC_SEL_SET(i) |
                AD9154_SHORT_TPL_SP_SEL_SET(0))
            # set expected value
            self.ad9154.dac_write(AD9154_SHORT_TPL_TEST_2, data & 0xff)
            self.ad9154.dac_write(AD9154_SHORT_TPL_TEST_1, (data & 0xff00) >> 8)
            # enable stpl
            self.ad9154.dac_write(AD9154_SHORT_TPL_TEST_0,
                AD9154_SHORT_TPL_TEST_EN_SET(1) |
                AD9154_SHORT_TPL_TEST_RESET_SET(0) |
                AD9154_SHORT_TPL_DAC_SEL_SET(i) |
                AD9154_SHORT_TPL_SP_SEL_SET(0))
            # reset stpl
            self.ad9154.dac_write(AD9154_SHORT_TPL_TEST_0,
                AD9154_SHORT_TPL_TEST_EN_SET(1) |
                AD9154_SHORT_TPL_TEST_RESET_SET(1) |
                AD9154_SHORT_TPL_DAC_SEL_SET(i) |
                AD9154_SHORT_TPL_SP_SEL_SET(0))
            # release reset stpl
            self.ad9154.dac_write(AD9154_SHORT_TPL_TEST_0,
                AD9154_SHORT_TPL_TEST_EN_SET(1) |
                AD9154_SHORT_TPL_TEST_RESET_SET(0) |
                AD9154_SHORT_TPL_DAC_SEL_SET(i) |
                AD9154_SHORT_TPL_SP_SEL_SET(0))
            print("c{:d}: {:d}".format(i, self.ad9154.dac_read(AD9154_SHORT_TPL_TEST_3)))
