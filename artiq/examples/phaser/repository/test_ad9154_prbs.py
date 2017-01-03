# TODO: move to firmware

from artiq.coredevice.ad9154_reg import *
from artiq.experiment import *


class Test(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("ad9154")

    @kernel
    def run(self):
        for e in range(2):
            for i in range(3):  # prbs7, prbs15, prbs31
                self.prbs(i, 10, e)

    @kernel
    def busywait_us(self, t):
        t = self.core.get_rtio_counter_mu() + self.core.seconds_to_mu(t*us)
        while self.core.get_rtio_counter_mu() < t:
            pass

    def p(self, f, *a):
        print(f.format(*a))

    @kernel
    def prbs(self, p, t, inject_errors):
        self.p("---\nprbs sequence {}, threshold {}, inject_errors {}:",
               p, t, inject_errors)
        self.ad9154.jesd_prbs((1 << p) | (inject_errors << 3))

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

        self.busywait_us(1000000)

        self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_CTRL, AD9154_PHY_PRBS_PAT_SEL_SET(p))

        self.p("prbs status: {:#04x}", self.ad9154.dac_read(AD9154_PHY_PRBS_TEST_STATUS))

        for i in range(8):
            self.ad9154.dac_write(AD9154_PHY_PRBS_TEST_CTRL, AD9154_PHY_SRC_ERR_CNT_SET(i))
            self.p("prbs errors[{}]: {:#08x}", i,
                    self.ad9154.dac_read(AD9154_PHY_PRBS_TEST_ERRCNT_LOBITS) |
                    (self.ad9154.dac_read(AD9154_PHY_PRBS_TEST_ERRCNT_MIDBITS) << 8) |
                    (self.ad9154.dac_read(AD9154_PHY_PRBS_TEST_ERRCNT_HIBITS) << 16))

        self.ad9154.jesd_prbs(0)
