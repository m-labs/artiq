# TODO: move to firmware

from jesd204b.transport import seed_to_data

from artiq.coredevice.ad9154_reg import *
from artiq.experiment import *


class Test(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ad9154")

    def run(self):
        self.ad9154.jesd_stpl(1)
        # short transport layer test
        for i in range(4):
            data = seed_to_data(i << 8, True)
            fail = self.stpl(i, data)
            print("channel", i, "FAIL" if fail else "PASS")
        self.ad9154.jesd_stpl(0)

    @kernel
    def stpl(self, i, data):
        # select dac
        self.ad9154.dac_write(AD9154_SHORT_TPL_TEST_0,
            AD9154_SHORT_TPL_TEST_EN_SET(0) |
            AD9154_SHORT_TPL_TEST_RESET_SET(0) |
            AD9154_SHORT_TPL_DAC_SEL_SET(i) |
            AD9154_SHORT_TPL_SP_SEL_SET(0))
        # set expected value
        self.ad9154.dac_write(AD9154_SHORT_TPL_TEST_1, data & 0xff)
        self.ad9154.dac_write(AD9154_SHORT_TPL_TEST_2, (data & 0xff00) >> 8)
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
        return self.ad9154.dac_read(AD9154_SHORT_TPL_TEST_3)
