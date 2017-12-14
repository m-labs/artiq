from artiq.coredevice.ad9154_reg import *
from artiq.experiment import *


class Test(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.ad9154_spi = self.get_device("ad9154_spi0")

    @kernel
    def run(self):
        self.ad9154_spi.setup_bus()
        self.print_prodid()
        self.print_status()
        self.print_temp()

    def p(self, f, *a):
        print(f % a)

    @kernel
    def print_prodid(self):
        self.p("PRODID: 0x%04x", (self.ad9154_spi.read(AD9154_PRODIDH) << 8) |
            self.ad9154_spi.read(AD9154_PRODIDL))

    @kernel
    def print_temp(self):
        self.ad9154_spi.write(AD9154_DIE_TEMP_CTRL0, AD9154_AUXADC_RESERVED_SET(0x10) |
                AD9154_AUXADC_ENABLE_SET(1))
        self.ad9154_spi.write(AD9154_DIE_TEMP_UPDATE, 1)
        self.p("temp_code %d", self.ad9154_spi.read(AD9154_DIE_TEMP0) |
                (self.ad9154_spi.read(AD9154_DIE_TEMP1) << 8))
        self.ad9154_spi.write(AD9154_DIE_TEMP_CTRL0, AD9154_AUXADC_RESERVED_SET(0x10) |
                AD9154_AUXADC_ENABLE_SET(0))

    @kernel
    def print_status(self):
        x = self.ad9154_spi.read(AD9154_IRQ_STATUS0)
        self.p("LANEFIFOERR: %d, SERPLLLOCK: %d, SERPLLLOST: %d, "
                "DACPLLLOCK: %d, DACPLLLOST: %d",
                AD9154_LANEFIFOERR_GET(x), AD9154_SERPLLLOCK_GET(x),
                AD9154_SERPLLLOST_GET(x), AD9154_DACPLLLOCK_GET(x),
                AD9154_DACPLLLOST_GET(x))
        x = self.ad9154_spi.read(AD9154_IRQ_STATUS1)
        self.p("PRBS0: %d, PRBS1: %d, PRBS2: %d, PRBS3: %d",
                AD9154_PRBS0_GET(x), AD9154_PRBS1_GET(x),
                AD9154_PRBS2_GET(x), AD9154_PRBS3_GET(x))
        x = self.ad9154_spi.read(AD9154_IRQ_STATUS2)
        self.p("SYNC_TRIP0: %d, SYNC_WLIM0: %d, SYNC_ROTATE0: %d, "
                "SYNC_LOCK0: %d, NCO_ALIGN0: %d, BLNKDONE0: %d, "
                "PDPERR0: %d",
                AD9154_SYNC_TRIP0_GET(x), AD9154_SYNC_WLIM0_GET(x),
                AD9154_SYNC_ROTATE0_GET(x), AD9154_SYNC_LOCK0_GET(x),
                AD9154_NCO_ALIGN0_GET(x), AD9154_BLNKDONE0_GET(x),
                AD9154_PDPERR0_GET(x))
        x = self.ad9154_spi.read(AD9154_IRQ_STATUS3)
        self.p("SYNC_TRIP1: %d, SYNC_WLIM1: %d, SYNC_ROTATE1: %d, "
                "SYNC_LOCK1: %d, NCO_ALIGN1: %d, BLNKDONE1: %d, "
                "PDPERR1: %d",
                AD9154_SYNC_TRIP1_GET(x), AD9154_SYNC_WLIM1_GET(x),
                AD9154_SYNC_ROTATE1_GET(x), AD9154_SYNC_LOCK1_GET(x),
                AD9154_NCO_ALIGN1_GET(x), AD9154_BLNKDONE1_GET(x),
                AD9154_PDPERR1_GET(x))
        x = self.ad9154_spi.read(AD9154_JESD_CHECKS)
        self.p("ERR_INTSUPP: %d, ERR_SUBCLASS: %d, ERR_KUNSUPP: %d, "
                "ERR_JESDBAD: %d, ERR_WINLIMIT: %d, ERR_DLYOVER: %d",
                AD9154_ERR_INTSUPP_GET(x), AD9154_ERR_SUBCLASS_GET(x),
                AD9154_ERR_KUNSUPP_GET(x), AD9154_ERR_JESDBAD_GET(x),
                AD9154_ERR_WINLIMIT_GET(x), AD9154_ERR_DLYOVER_GET(x))

        x = self.ad9154_spi.read(AD9154_DACPLLSTATUS)
        self.p("DACPLL_LOCK: %d, VCO_CAL_PROGRESS: %d, CP_CAL_VALID: %d, "
                "CP_OVERRANGE_L: %d, CP_OVERRANGE_H: %d",
                AD9154_DACPLL_LOCK_GET(x), AD9154_VCO_CAL_PROGRESS_GET(x),
                AD9154_CP_CAL_VALID_GET(x), AD9154_CP_OVERRANGE_L_GET(x),
                AD9154_CP_OVERRANGE_H_GET(x))

        x = self.ad9154_spi.read(AD9154_PLL_STATUS)
        self.p("PLL_LOCK_RB: %d, CURRENTS_READY_RB: %d, "
                "VCO_CAL_IN_PROGRESS_RB: %d, PLL_CAL_VALID_RB: %d, "
                "PLL_OVERRANGE_L_RB: %d, PLL_OVERRANGE_H_RB: %d",
                AD9154_SERDES_PLL_LOCK_RB_GET(x),
                AD9154_SERDES_CURRENTS_READY_RB_GET(x),
                AD9154_SERDES_VCO_CAL_IN_PROGRESS_RB_GET(x),
                AD9154_SERDES_PLL_CAL_VALID_RB_GET(x),
                AD9154_SERDES_PLL_OVERRANGE_L_RB_GET(x),
                AD9154_SERDES_PLL_OVERRANGE_H_RB_GET(x))

        self.p("CODEGRPSYNC: 0x%02x", self.ad9154_spi.read(AD9154_CODEGRPSYNCFLG))
        self.p("FRAMESYNC: 0x%02x", self.ad9154_spi.read(AD9154_FRAMESYNCFLG))
        self.p("GOODCHECKSUM: 0x%02x", self.ad9154_spi.read(AD9154_GOODCHKSUMFLG))
        self.p("INITIALLANESYNC: 0x%02x", self.ad9154_spi.read(AD9154_INITLANESYNCFLG))

        x = self.ad9154_spi.read(AD9154_SYNC_CURRERR_H)
        self.p("SYNC_CURRERR: 0x%04x", self.ad9154_spi.read(AD9154_SYNC_CURRERR_L) |
                    (AD9154_CURRERROR_H_GET(x) << 8))
        self.p("SYNC_CURROVER: %d, SYNC_CURRUNDER: %d",
                AD9154_CURROVER_GET(x), AD9154_CURRUNDER_GET(x))
        x = self.ad9154_spi.read(AD9154_SYNC_LASTERR_H)
        self.p("SYNC_LASTERR: 0x%04x", self.ad9154_spi.read(AD9154_SYNC_LASTERR_L) |
                    (AD9154_LASTERROR_H_GET(x) << 8))
        self.p("SYNC_LASTOVER: %d, SYNC_LASTUNDER: %d",
                AD9154_LASTOVER_GET(x), AD9154_LASTUNDER_GET(x))
        x = self.ad9154_spi.read(AD9154_SYNC_STATUS)
        self.p("SYNC_TRIP: %d, SYNC_WLIM: %d, SYNC_ROTATE: %d, "
                "SYNC_LOCK: %d, SYNC_BUSY: %d",
                AD9154_SYNC_TRIP_GET(x), AD9154_SYNC_WLIM_GET(x),
                AD9154_SYNC_ROTATE_GET(x), AD9154_SYNC_LOCK_GET(x),
                AD9154_SYNC_BUSY_GET(x))

        self.p("LANE_FIFO_FULL: 0x%02x", self.ad9154_spi.read(AD9154_FIFO_STATUS_REG_0))
        self.p("LANE_FIFO_EMPTY: 0x%02x", self.ad9154_spi.read(AD9154_FIFO_STATUS_REG_1))
        self.p("DID_REG: 0x%02x", self.ad9154_spi.read(AD9154_DID_REG))
        self.p("BID_REG: 0x%02x", self.ad9154_spi.read(AD9154_BID_REG))
        self.p("SCR_L_REG: 0x%02x", self.ad9154_spi.read(AD9154_SCR_L_REG))
        self.p("F_REG: 0x%02x", self.ad9154_spi.read(AD9154_F_REG))
        self.p("K_REG: 0x%02x", self.ad9154_spi.read(AD9154_K_REG))
        self.p("M_REG: 0x%02x", self.ad9154_spi.read(AD9154_M_REG))
        self.p("CS_N_REG: 0x%02x", self.ad9154_spi.read(AD9154_CS_N_REG))
        self.p("NP_REG: 0x%02x", self.ad9154_spi.read(AD9154_NP_REG))
        self.p("S_REG: 0x%02x", self.ad9154_spi.read(AD9154_S_REG))
        self.p("HD_CF_REG: 0x%02x", self.ad9154_spi.read(AD9154_HD_CF_REG))
        self.p("RES1_REG: 0x%02x", self.ad9154_spi.read(AD9154_RES1_REG))
        self.p("RES2_REG: 0x%02x", self.ad9154_spi.read(AD9154_RES2_REG))
        self.p("LIDx_REG: 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x",
                self.ad9154_spi.read(AD9154_LID0_REG), self.ad9154_spi.read(AD9154_LID1_REG),
                self.ad9154_spi.read(AD9154_LID2_REG), self.ad9154_spi.read(AD9154_LID3_REG),
                self.ad9154_spi.read(AD9154_LID4_REG), self.ad9154_spi.read(AD9154_LID5_REG),
                self.ad9154_spi.read(AD9154_LID6_REG), self.ad9154_spi.read(AD9154_LID7_REG))
        self.p("CHECKSUMx_REG: 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x",
                self.ad9154_spi.read(AD9154_CHECKSUM0_REG), self.ad9154_spi.read(AD9154_CHECKSUM1_REG),
                self.ad9154_spi.read(AD9154_CHECKSUM2_REG), self.ad9154_spi.read(AD9154_CHECKSUM3_REG),
                self.ad9154_spi.read(AD9154_CHECKSUM4_REG), self.ad9154_spi.read(AD9154_CHECKSUM5_REG),
                self.ad9154_spi.read(AD9154_CHECKSUM6_REG), self.ad9154_spi.read(AD9154_CHECKSUM7_REG))
        self.p("COMPSUMx_REG: 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x 0x%02x",
                self.ad9154_spi.read(AD9154_COMPSUM0_REG), self.ad9154_spi.read(AD9154_COMPSUM1_REG),
                self.ad9154_spi.read(AD9154_COMPSUM2_REG), self.ad9154_spi.read(AD9154_COMPSUM3_REG),
                self.ad9154_spi.read(AD9154_COMPSUM4_REG), self.ad9154_spi.read(AD9154_COMPSUM5_REG),
                self.ad9154_spi.read(AD9154_COMPSUM6_REG), self.ad9154_spi.read(AD9154_COMPSUM7_REG))
        self.p("BADDISPARITY: 0x%02x", self.ad9154_spi.read(AD9154_BADDISPARITY))
        self.p("NITDISPARITY: 0x%02x", self.ad9154_spi.read(AD9154_NIT_W))
        self.p("UNEXPECTEDCONTROL: 0x%02x", self.ad9154_spi.read(AD9154_UNEXPECTEDCONTROL_W))
        self.p("DYN_LINK_LATENCY_0: 0x%02x",
               self.ad9154_spi.read(AD9154_DYN_LINK_LATENCY_0))
        self.p("DYN_LINK_LATENCY_1: 0x%02x",
               self.ad9154_spi.read(AD9154_DYN_LINK_LATENCY_1))
