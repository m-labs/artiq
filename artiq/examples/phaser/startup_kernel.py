from jesd204b.common import (JESD204BPhysicalSettings,
                             JESD204BTransportSettings,
                             JESD204BSettings)
from artiq.experiment import *
from artiq.coredevice.ad9516_reg import *
from artiq.coredevice.ad9154_reg import *

# ad9154 mode 2:
ps = JESD204BPhysicalSettings(
    l=4,            # lanes
    m=4,            # converters
    n=16,           # bits/converter
    np=16,          # bits/sample
    sc=250*1e6,     # data clock, unused: FIXME
)
ts = JESD204BTransportSettings(
    f=2,            # octets/(lane and frame)
    s=1,            # samples/(converter and frame)
    k=16,           # frames/multiframe
    cs=1,           #
)
jesd_settings = JESD204BSettings(ps, ts, did=0x5a, bid=0x5)
jesd_checksum = jesd_settings.get_configuration_data()[-1]
jesd_data_freq = 250e6
jesd_linerate = 5e9
# external clk=2000MHz
# pclock=250MHz
# deviceclock_fpga=500MHz
# deviceclock_dac=2000MHz


class StartupKernel(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("led")
        self.setattr_device("ad9154")

    @kernel
    def run(self):
        self.core.reset()
        self.ad9154.jesd_enable(0)
        self.ad9154.init()
        self.clock_setup()
        self.dac_setup()
        self.ad9154.jesd_prbs(0)
        t = now_mu() + seconds_to_mu(.1*s)
        while self.core.get_rtio_counter_mu() < t:
            pass
        self.ad9154.jesd_enable(1)

    @kernel
    def clock_setup(self):
        # reset
        self.ad9154.clock_write(AD9516_SERIAL_PORT_CONFIGURATION,
                AD9516_SOFT_RESET | AD9516_SOFT_RESET_MIRRORED |
                AD9516_LONG_INSTRUCTION | AD9516_LONG_INSTRUCTION_MIRRORED |
                AD9516_SDO_ACTIVE | AD9516_SDO_ACTIVE_MIRRORED)
        self.ad9154.clock_write(AD9516_SERIAL_PORT_CONFIGURATION,
                AD9516_LONG_INSTRUCTION | AD9516_LONG_INSTRUCTION_MIRRORED |
                AD9516_SDO_ACTIVE | AD9516_SDO_ACTIVE_MIRRORED)
        if self.ad9154.clock_read(AD9516_PART_ID) != 0x41:
            return

        # use clk input, dclk=clk/4
        self.ad9154.clock_write(AD9516_PFD_AND_CHARGE_PUMP, 1*AD9516_PLL_POWER_DOWN |
                0*AD9516_CHARGE_PUMP_MODE)
        self.ad9154.clock_write(AD9516_VCO_DIVIDER, 2)
        self.ad9154.clock_write(AD9516_INPUT_CLKS, 0*AD9516_SELECT_VCO_OR_CLK |
                0*AD9516_BYPASS_VCO_DIVIDER)

        self.ad9154.clock_write(AD9516_OUT0, 2*AD9516_OUT0_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT2, 2*AD9516_OUT2_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT3, 2*AD9516_OUT3_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT4, 2*AD9516_OUT4_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT5, 2*AD9516_OUT5_POWER_DOWN)
        self.ad9154.clock_write(AD9516_OUT8, 1*AD9516_OUT8_POWER_DOWN)

        # DAC deviceclk, clk/1
        self.ad9154.clock_write(AD9516_DIVIDER_0_2, AD9516_DIVIDER_0_DIRECT_TO_OUTPUT)
        self.ad9154.clock_write(AD9516_OUT1, 0*AD9516_OUT1_POWER_DOWN |
                2*AD9516_OUT1_LVPECLDIFFERENTIAL_VOLTAGE)

        # FPGA deviceclk, dclk/1
        self.ad9154.clock_write(AD9516_DIVIDER_4_3, AD9516_DIVIDER_4_BYPASS_1 |
                AD9516_DIVIDER_4_BYPASS_2)
        self.ad9154.clock_write(AD9516_DIVIDER_4_4, 1*AD9516_DIVIDER_4_DCCOFF)
        self.ad9154.clock_write(AD9516_OUT9, 1*AD9516_OUT9_LVDS_OUTPUT_CURRENT |
                2*AD9516_OUT9_LVDS_CMOS_OUTPUT_POLARITY |
                0*AD9516_OUT9_SELECT_LVDS_CMOS)

        # sysref f_data*S/(K*F), dclk/32
        self.ad9154.clock_write(AD9516_DIVIDER_3_0, 15*AD9516_DIVIDER_3_HIGH_CYCLES_1 |
                15*AD9516_DIVIDER_3_LOW_CYCLES_1)
        self.ad9154.clock_write(AD9516_DIVIDER_3_1, 0*AD9516_DIVIDER_3_PHASE_OFFSET_1 |
                0*AD9516_DIVIDER_3_PHASE_OFFSET_2)
        self.ad9154.clock_write(AD9516_DIVIDER_3_3, 0*AD9516_DIVIDER_3_NOSYNC |
                0*AD9516_DIVIDER_3_BYPASS_1 | 1*AD9516_DIVIDER_3_BYPASS_2)
        self.ad9154.clock_write(AD9516_DIVIDER_3_4, 1*AD9516_DIVIDER_3_DCCOFF)
        self.ad9154.clock_write(AD9516_OUT6, 1*AD9516_OUT6_LVDS_OUTPUT_CURRENT |
                2*AD9516_OUT6_LVDS_CMOS_OUTPUT_POLARITY |
                0*AD9516_OUT6_SELECT_LVDS_CMOS)
        self.ad9154.clock_write(AD9516_OUT7, 1*AD9516_OUT7_LVDS_OUTPUT_CURRENT |
                2*AD9516_OUT7_LVDS_CMOS_OUTPUT_POLARITY |
                0*AD9516_OUT7_SELECT_LVDS_CMOS)

        self.ad9154.clock_write(AD9516_UPDATE_ALL_REGISTERS, 1)

    @kernel
    def dac_setup(self):
        # reset
        self.ad9154.dac_write(AD9154_SPI_INTFCONFA, AD9154_SOFTRESET_SET(1) |
                AD9154_LSBFIRST_SET(0) | AD9154_SDOACTIVE_SET(1))
        self.ad9154.dac_write(AD9154_SPI_INTFCONFA,
                AD9154_LSBFIRST_SET(0) | AD9154_SDOACTIVE_SET(1))
        if ((self.ad9154.dac_read(AD9154_PRODIDH) << 8) |
                self.ad9154.dac_read(AD9154_PRODIDL) != 0x9154):
            return

        self.ad9154.dac_write(AD9154_PWRCNTRL0,
                AD9154_PD_DAC0_SET(0) | AD9154_PD_DAC1_SET(0) |
                AD9154_PD_DAC2_SET(0) | AD9154_PD_DAC3_SET(0) |
                AD9154_PD_BG_SET(0))
        self.ad9154.dac_write(AD9154_TXENMASK1, AD9154_DACA_MASK_SET(0) |
                AD9154_DACB_MASK_SET(0))  # TX not controlled by TXEN pins
        self.ad9154.dac_write(AD9154_CLKCFG0,
                AD9154_REF_CLKDIV_EN_SET(0) | AD9154_RF_SYNC_EN_SET(1) |
                AD9154_DUTY_EN_SET(1) | AD9154_PD_CLK_REC_SET(0) |
                AD9154_PD_SERDES_PCLK_SET(0) | AD9154_PD_CLK_DIG_SET(0) |
                AD9154_PD_CLK23_SET(0) | AD9154_PD_CLK01_SET(0))
        self.ad9154.dac_write(AD9154_DACPLLCNTRL,
                AD9154_ENABLE_DACPLL_SET(0) | AD9154_RECAL_DACPLL_SET(0))
        self.ad9154.dac_write(AD9154_SYSREF_ACTRL0, # jesd204b subclass 1
                AD9154_HYS_CNTRL1_SET(0) | AD9154_SYSREF_RISE_SET(0) |
                AD9154_HYS_ON_SET(0) | AD9154_PD_SYSREF_BUFFER_SET(0))

        self.ad9154.dac_write(AD9154_DEVICE_CONFIG_REG_0, 0x8b) # magic
        self.ad9154.dac_write(AD9154_DEVICE_CONFIG_REG_1, 0x01) # magic
        self.ad9154.dac_write(AD9154_DEVICE_CONFIG_REG_2, 0x01) # magic

        self.ad9154.dac_write(AD9154_SPI_PAGEINDX, 0x3) # A and B dual

        self.ad9154.dac_write(AD9154_INTERP_MODE, 4) # 8x
        self.ad9154.dac_write(AD9154_MIX_MODE, 0)
        self.ad9154.dac_write(AD9154_DATA_FORMAT, AD9154_BINARY_FORMAT_SET(0)) # s16
        self.ad9154.dac_write(AD9154_DATAPATH_CTRL,
                AD9154_I_TO_Q_SET(0) | AD9154_SEL_SIDEBAND_SET(0) |
                AD9154_MODULATION_TYPE_SET(0) | AD9154_PHASE_ADJ_ENABLE_SET(0) |
                AD9154_DIG_GAIN_ENABLE_SET(0) | AD9154_INVSINC_ENABLE_SET(0))
        self.ad9154.dac_write(AD9154_IDAC_DIG_GAIN0, 0x00)
        self.ad9154.dac_write(AD9154_IDAC_DIG_GAIN1, 0x8)
        self.ad9154.dac_write(AD9154_QDAC_DIG_GAIN0, 0x00)
        self.ad9154.dac_write(AD9154_QDAC_DIG_GAIN1, 0x8)
        self.ad9154.dac_write(AD9154_DC_OFFSET_CTRL, 0)
        self.ad9154.dac_write(AD9154_IPATH_DC_OFFSET_1PART0, 0x00)
        self.ad9154.dac_write(AD9154_IPATH_DC_OFFSET_1PART1, 0x00)
        self.ad9154.dac_write(AD9154_IPATH_DC_OFFSET_2PART, 0x00)
        self.ad9154.dac_write(AD9154_QPATH_DC_OFFSET_1PART0, 0x00)
        self.ad9154.dac_write(AD9154_QPATH_DC_OFFSET_1PART1, 0x00)
        self.ad9154.dac_write(AD9154_QPATH_DC_OFFSET_2PART, 0x00)
        self.ad9154.dac_write(AD9154_PHASE_ADJ0, 0)
        self.ad9154.dac_write(AD9154_PHASE_ADJ1, 0)
        self.ad9154.dac_write(AD9154_GROUP_DLY, AD9154_COARSE_GROUP_DELAY_SET(0x8) |
                AD9154_GROUP_DELAY_RESERVED_SET(0x8))
        self.ad9154.dac_write(AD9154_GROUPDELAY_COMP_BYP,
                AD9154_GROUPCOMP_BYPQ_SET(1) |
                AD9154_GROUPCOMP_BYPI_SET(1))
        self.ad9154.dac_write(AD9154_GROUPDELAY_COMP_I, 0)
        self.ad9154.dac_write(AD9154_GROUPDELAY_COMP_Q, 0)
        self.ad9154.dac_write(AD9154_PDP_AVG_TIME, AD9154_PDP_ENABLE_SET(0))

        self.ad9154.dac_write(AD9154_MASTER_PD, 0)
        self.ad9154.dac_write(AD9154_PHY_PD, 0x0f) # power down lanes 0-3
        self.ad9154.dac_write(AD9154_GENERIC_PD,
                AD9154_PD_SYNCOUT0B_SET(0) |
                AD9154_PD_SYNCOUT1B_SET(1))
        self.ad9154.dac_write(AD9154_GENERAL_JRX_CTRL_0,
                AD9154_LINK_EN_SET(0x0) | AD9154_LINK_PAGE_SET(0) |
                AD9154_LINK_MODE_SET(0) | AD9154_CHECKSUM_MODE_SET(0))
        self.ad9154.dac_write(AD9154_ILS_DID, jesd_settings.did)
        self.ad9154.dac_write(AD9154_ILS_BID, jesd_settings.bid)
        self.ad9154.dac_write(AD9154_ILS_LID0, 0x00) # lane id
        self.ad9154.dac_write(AD9154_ILS_SCR_L,
                              AD9154_L_1_SET(jesd_settings.phy.l - 1) |
                              AD9154_SCR_SET(1))
        self.ad9154.dac_write(AD9154_ILS_F, jesd_settings.transport.f - 1)
        self.ad9154.dac_write(AD9154_ILS_K, jesd_settings.transport.k - 1)
        self.ad9154.dac_write(AD9154_ILS_M, jesd_settings.phy.m - 1)
        self.ad9154.dac_write(AD9154_ILS_CS_N,
                              AD9154_N_1_SET(jesd_settings.phy.n - 1) |
                              AD9154_CS_SET(0))
        self.ad9154.dac_write(AD9154_ILS_NP,
                              AD9154_NP_1_SET(jesd_settings.phy.np - 1) |
                              AD9154_SUBCLASSV_SET(jesd_settings.phy.subclassv))
        self.ad9154.dac_write(AD9154_ILS_S,
                              AD9154_S_1_SET(jesd_settings.transport.s - 1) |
                              AD9154_JESDV_SET(jesd_settings.phy.jesdv))
        self.ad9154.dac_write(AD9154_ILS_HD_CF,
                              AD9154_HD_SET(0) | AD9154_CF_SET(0))
        self.ad9154.dac_write(AD9154_ILS_CHECKSUM, jesd_checksum)
        self.ad9154.dac_write(AD9154_LANEDESKEW, 0x0f)
        for i in range(8):
            self.ad9154.dac_write(AD9154_BADDISPARITY, AD9154_RST_IRQ_DIS_SET(0) |
                    AD9154_DISABLE_ERR_CNTR_DIS_SET(0) |
                    AD9154_RST_ERR_CNTR_DIS_SET(1) | AD9154_LANE_ADDR_DIS_SET(i))
            self.ad9154.dac_write(AD9154_BADDISPARITY, AD9154_RST_IRQ_DIS_SET(0) |
                    AD9154_DISABLE_ERR_CNTR_DIS_SET(0) |
                    AD9154_RST_ERR_CNTR_DIS_SET(0) | AD9154_LANE_ADDR_DIS_SET(i))
            self.ad9154.dac_write(AD9154_NIT_W, AD9154_RST_IRQ_NIT_SET(0) |
                    AD9154_DISABLE_ERR_CNTR_NIT_SET(0) |
                    AD9154_RST_ERR_CNTR_NIT_SET(1) | AD9154_LANE_ADDR_NIT_SET(i))
            self.ad9154.dac_write(AD9154_NIT_W, AD9154_RST_IRQ_NIT_SET(0) |
                    AD9154_DISABLE_ERR_CNTR_NIT_SET(0) |
                    AD9154_RST_ERR_CNTR_NIT_SET(0) | AD9154_LANE_ADDR_NIT_SET(i))
            self.ad9154.dac_write(AD9154_UNEXPECTEDCONTROL_W, AD9154_RST_IRQ_UCC_SET(0) |
                    AD9154_DISABLE_ERR_CNTR_UCC_SET(0) |
                    AD9154_RST_ERR_CNTR_UCC_SET(1) | AD9154_LANE_ADDR_UCC_SET(i))
            self.ad9154.dac_write(AD9154_BADDISPARITY, AD9154_RST_IRQ_UCC_SET(0) |
                    AD9154_DISABLE_ERR_CNTR_UCC_SET(0) |
                    AD9154_RST_ERR_CNTR_UCC_SET(0) | AD9154_LANE_ADDR_UCC_SET(i))
        self.ad9154.dac_write(AD9154_CTRLREG1, jesd_settings.transport.f)
        self.ad9154.dac_write(AD9154_CTRLREG2, AD9154_ILAS_MODE_SET(0) |
                AD9154_THRESHOLD_MASK_EN_SET(0))
        self.ad9154.dac_write(AD9154_KVAL, 1) # *4*K multiframes during ILAS
        self.ad9154.dac_write(AD9154_LANEENABLE, 0x0f)

        self.ad9154.dac_write(AD9154_TERM_BLK1_CTRLREG0, 1)
        self.ad9154.dac_write(AD9154_TERM_BLK2_CTRLREG0, 1)
        self.ad9154.dac_write(AD9154_SERDES_SPI_REG, 1)
        self.ad9154.dac_write(AD9154_CDR_OPERATING_MODE_REG_0,
                AD9154_CDR_OVERSAMP_SET(0) | AD9154_CDR_RESERVED_SET(0x2) |
                AD9154_ENHALFRATE_SET(0))
        self.ad9154.dac_write(AD9154_CDR_RESET, 0)
        self.ad9154.dac_write(AD9154_CDR_RESET, 1)
        self.ad9154.dac_write(AD9154_REF_CLK_DIVIDER_LDO,
                AD9154_SPI_CDR_OVERSAMP_SET(0x1) |
                AD9154_SPI_LDO_BYPASS_FILT_SET(1) |
                AD9154_SPI_LDO_REF_SEL_SET(0))
        self.ad9154.dac_write(AD9154_LDO_FILTER_1, 0x62) # magic
        self.ad9154.dac_write(AD9154_LDO_FILTER_2, 0xc9) # magic
        self.ad9154.dac_write(AD9154_LDO_FILTER_3, 0x0e) # magic
        self.ad9154.dac_write(AD9154_CP_CURRENT_SPI,
                AD9154_SPI_CP_CURRENT_SET(0x12) |
                AD9154_SPI_SERDES_LOGEN_POWER_MODE_SET(0))
        self.ad9154.dac_write(AD9154_VCO_LDO, 0x7b) # magic
        self.ad9154.dac_write(AD9154_PLL_RD_REG,
                AD9154_SPI_SERDES_LOGEN_PD_CORE_SET(0) |
                AD9154_SPI_SERDES_LDO_PD_SET(0) | AD9154_SPI_SYN_PD_SET(0) |
                AD9154_SPI_VCO_PD_ALC_SET(0) | AD9154_SPI_VCO_PD_PTAT_SET(0) |
                AD9154_SPI_VCO_PD_SET(0))
        self.ad9154.dac_write(AD9154_ALC_VARACTOR,
                AD9154_SPI_VCO_VARACTOR_SET(0x9) |
                AD9154_SPI_INIT_ALC_VALUE_SET(0x8))
        self.ad9154.dac_write(AD9154_VCO_OUTPUT,
                AD9154_SPI_VCO_OUTPUT_LEVEL_SET(0xc) |
                AD9154_SPI_VCO_OUTPUT_RESERVED_SET(0x4))
        self.ad9154.dac_write(AD9154_CP_CONFIG,
                AD9154_SPI_CP_TEST_SET(0) |
                AD9154_SPI_CP_CAL_EN_SET(1) |
                AD9154_SPI_CP_FORCE_CALBITS_SET(0) |
                AD9154_SPI_CP_OFFSET_OFF_SET(0) |
                AD9154_SPI_CP_ENABLE_MACHINE_SET(1) |
                AD9154_SPI_CP_DITHER_MODE_SET(0) |
                AD9154_SPI_CP_HALF_VCO_CAL_CLK_SET(0))
        self.ad9154.dac_write(AD9154_VCO_BIAS_1,
                AD9154_SPI_VCO_BIAS_REF_SET(0x3) |
                AD9154_SPI_VCO_BIAS_TCF_SET(0x3))
        self.ad9154.dac_write(AD9154_VCO_BIAS_2,
                AD9154_SPI_PRESCALE_BIAS_SET(0x1) |
                AD9154_SPI_LAST_ALC_EN_SET(1) |
                AD9154_SPI_PRESCALE_BYPASS_R_SET(0x1) |
                AD9154_SPI_VCO_COMP_BYPASS_BIASR_SET(0) |
                AD9154_SPI_VCO_BYPASS_DAC_R_SET(0))
        self.ad9154.dac_write(AD9154_VCO_PD_OVERRIDES,
                AD9154_SPI_VCO_PD_OVERRIDE_VCO_BUF_SET(0) |
                AD9154_SPI_VCO_PD_OVERRIDE_CAL_TCF_SET(1) |
                AD9154_SPI_VCO_PD_OVERRIDE_VAR_REF_TCF_SET(0) |
                AD9154_SPI_VCO_PD_OVERRIDE_VAR_REF_SET(0))
        self.ad9154.dac_write(AD9154_VCO_CAL,
                AD9154_SPI_FB_CLOCK_ADV_SET(0x2) |
                AD9154_SPI_VCO_CAL_COUNT_SET(0x3) |
                AD9154_SPI_VCO_CAL_ALC_WAIT_SET(0) |
                AD9154_SPI_VCO_CAL_EN_SET(1))
        self.ad9154.dac_write(AD9154_CP_LEVEL_DETECT,
                AD9154_SPI_CP_LEVEL_THRESHOLD_HIGH_SET(0x2) |
                AD9154_SPI_CP_LEVEL_THRESHOLD_LOW_SET(0x5) |
                AD9154_SPI_CP_LEVEL_DET_PD_SET(0))
        self.ad9154.dac_write(AD9154_VCO_VARACTOR_CTRL_0,
                AD9154_SPI_VCO_VARACTOR_OFFSET_SET(0xe) |
                AD9154_SPI_VCO_VARACTOR_REF_TCF_SET(0x7))
        self.ad9154.dac_write(AD9154_VCO_VARACTOR_CTRL_1,
                AD9154_SPI_VCO_VARACTOR_REF_SET(0x6))
        # ensure link is txing
        self.ad9154.dac_write(AD9154_SERDESPLL_ENABLE_CNTRL,
                AD9154_ENABLE_SERDESPLL_SET(1) | AD9154_RECAL_SERDESPLL_SET(1))
        self.ad9154.dac_write(AD9154_SERDESPLL_ENABLE_CNTRL,
                AD9154_ENABLE_SERDESPLL_SET(1) | AD9154_RECAL_SERDESPLL_SET(0))
        self.ad9154.dac_write(AD9154_EQ_BIAS_REG, AD9154_EQ_BIAS_RESERVED_SET(0x22) |
                AD9154_EQ_POWER_MODE_SET(1))

        self.ad9154.dac_write(AD9154_GENERAL_JRX_CTRL_1, 1) # subclass 1
        self.ad9154.dac_write(AD9154_LMFC_DELAY_0, 0)
        self.ad9154.dac_write(AD9154_LMFC_DELAY_1, 0)
        self.ad9154.dac_write(AD9154_LMFC_VAR_0, 0x0a) # receive buffer delay
        self.ad9154.dac_write(AD9154_LMFC_VAR_1, 0x0a)
        self.ad9154.dac_write(AD9154_SYNC_ERRWINDOW, 0) # +- 1/2 DAC clock
        self.ad9154.dac_write(AD9154_SYNC_CONTROL,
                AD9154_SYNCMODE_SET(1) | AD9154_SYNCENABLE_SET(0) |
                AD9154_SYNCARM_SET(0))
        self.ad9154.dac_write(AD9154_SYNC_CONTROL,
                AD9154_SYNCMODE_SET(1) | AD9154_SYNCENABLE_SET(1) |
                AD9154_SYNCARM_SET(0))
        self.ad9154.dac_write(AD9154_SYNC_CONTROL,
                AD9154_SYNCMODE_SET(1) | AD9154_SYNCENABLE_SET(1) |
                AD9154_SYNCARM_SET(1))
        self.ad9154.dac_write(AD9154_XBAR_LN_0_1,
                AD9154_LOGICAL_LANE0_SRC_SET(7) | AD9154_LOGICAL_LANE1_SRC_SET(6))
        self.ad9154.dac_write(AD9154_XBAR_LN_2_3,
                AD9154_LOGICAL_LANE2_SRC_SET(5) | AD9154_LOGICAL_LANE3_SRC_SET(4))
        self.ad9154.dac_write(AD9154_XBAR_LN_4_5,
                AD9154_LOGICAL_LANE4_SRC_SET(0) | AD9154_LOGICAL_LANE5_SRC_SET(0))
        self.ad9154.dac_write(AD9154_XBAR_LN_6_7,
                AD9154_LOGICAL_LANE6_SRC_SET(0) | AD9154_LOGICAL_LANE7_SRC_SET(0))
        self.ad9154.dac_write(AD9154_JESD_BIT_INVERSE_CTRL, 0x00)
        self.ad9154.dac_write(AD9154_GENERAL_JRX_CTRL_0,
                AD9154_LINK_EN_SET(0x1) | AD9154_LINK_PAGE_SET(0) |
                AD9154_LINK_MODE_SET(0) | AD9154_CHECKSUM_MODE_SET(0))
