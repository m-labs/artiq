import time

from artiq.coredevice.ad9154_reg import *
from artiq.experiment import *


class Test(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ad9154")

    def run(self):
        self.prbs(2, 100)  # prbs31

    def p(self, f, *a):
        print(f % a)

    def prbs(self, p, t):
        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_CTRL,
                AD9154_PHY_PRBS_PAT_SEL_SET(p))
        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_EN, 0xff)
        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_CTRL,
                AD9154_PHY_PRBS_PAT_SEL_SET(p) | AD9154_PHY_TEST_RESET_SET(1))
        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_CTRL,
                AD9154_PHY_PRBS_PAT_SEL_SET(p))

        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_THRESHOLD_LOBITS, t)
        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_THRESHOLD_MIDBITS, t >> 8)
        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_THRESHOLD_MIDBITS, t >> 16)

        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_CTRL, AD9154_PHY_PRBS_PAT_SEL_SET(p))
        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_CTRL,
                AD9154_PHY_PRBS_PAT_SEL_SET(p) | AD9154_PHY_TEST_START_SET(1))

        time.sleep(.5)

        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_CTRL, AD9154_PHY_PRBS_PAT_SEL_SET(p))

        self.p("prbs status: 0x%02x", self.ad9154.dac_read(AD9154_PHY_PRBS_TEST_STATUS))

        for i in range(8):
            self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_CTRL, AD9154_PHY_SRC_ERR_CNT_SET(i))
            self.p("prbs errors[%d]: 0x%08x", i,
                    self.ad9154.dac_read(AD9154_PHY_PRBS_TEST_ERRCNT_LOBITS) |
                    (self.ad9154.dac_read(AD9154_PHY_PRBS_TEST_ERRCNT_MIDBITS) << 8) |
                    (self.ad9154.dac_read(AD9154_PHY_PRBS_TEST_ERRCNT_HIBITS) << 16))
