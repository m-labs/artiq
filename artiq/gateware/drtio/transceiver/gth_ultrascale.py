from functools import reduce
from operator import or_, and_

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from misoc.cores.code_8b10b import Encoder, Decoder

from microscope import *

from artiq.gateware.drtio.core import TransceiverInterface, ChannelInterface
from artiq.gateware.drtio.transceiver.clock_aligner import BruteforceClockAligner
from artiq.gateware.drtio.transceiver.gth_ultrascale_init import *


class GTHSingle(Module):
    def __init__(self, refclk, pads, sys_clk_freq, rtio_clk_freq, rtiox_mul, dw, mode):
        assert (dw == 20) or (dw == 40)
        assert mode in ["single", "master", "slave"]
        self.mode = mode

        # phase alignment
        self.txsyncallin = Signal()
        self.txphaligndone = Signal()
        self.txsyncallin = Signal()
        self.txsyncin = Signal()
        self.txsyncout = Signal()
        self.txdlysreset = Signal()

        # # #

        nwords = dw//10
        self.submodules.encoder = encoder = ClockDomainsRenamer("rtio_tx")(
            Encoder(nwords, True))
        self.submodules.decoders = decoders = [ClockDomainsRenamer("rtio_rx")(
            (Decoder(True))) for _ in range(nwords)]
        self.rx_ready = Signal()

        # transceiver direct clock outputs
        # for OBUFDS_GTE3
        self.rxrecclkout = Signal()
        # useful to specify clock constraints in a way palatable to Vivado
        self.txoutclk = Signal()
        self.rxoutclk = Signal()

        # # #

        # TX generates RTIO clock, init must be in system domain
        self.submodules.tx_init = tx_init = GTHInit(sys_clk_freq, False, mode)
        # RX receives restart commands from RTIO domain
        rx_init = ClockDomainsRenamer("rtio_tx")(GTHInit(rtio_clk_freq, True))
        self.submodules += rx_init

        cpll_reset = Signal()
        cpll_lock = Signal()
        self.comb += [
            cpll_reset.eq(tx_init.pllreset),
            tx_init.plllock.eq(cpll_lock),
            rx_init.plllock.eq(cpll_lock)
        ]

        txdata = Signal(dw)
        rxdata = Signal(dw)
        rxphaligndone = Signal()
        gth_params = dict(
            p_ACJTAG_DEBUG_MODE              =0b0,
            p_ACJTAG_MODE                    =0b0,
            p_ACJTAG_RESET                   =0b0,
            p_ADAPT_CFG0                     =0b1111100000000000,
            p_ADAPT_CFG1                     =0b0000000000000000,
            p_ALIGN_COMMA_DOUBLE             ="FALSE",
            p_ALIGN_COMMA_ENABLE             =0b0000000000,
            p_ALIGN_COMMA_WORD               =1,
            p_ALIGN_MCOMMA_DET               ="FALSE",
            p_ALIGN_MCOMMA_VALUE             =0b1010000011,
            p_ALIGN_PCOMMA_DET               ="FALSE",
            p_ALIGN_PCOMMA_VALUE             =0b0101111100,
            p_A_RXOSCALRESET                 =0b0,
            p_A_RXPROGDIVRESET               =0b0,
            p_A_TXPROGDIVRESET               =0b0,
            p_CBCC_DATA_SOURCE_SEL           ="ENCODED",
            p_CDR_SWAP_MODE_EN               =0b0,
            p_CHAN_BOND_KEEP_ALIGN           ="FALSE",
            p_CHAN_BOND_MAX_SKEW             =1,
            p_CHAN_BOND_SEQ_1_1              =0b0000000000,
            p_CHAN_BOND_SEQ_1_2              =0b0000000000,
            p_CHAN_BOND_SEQ_1_3              =0b0000000000,
            p_CHAN_BOND_SEQ_1_4              =0b0000000000,
            p_CHAN_BOND_SEQ_1_ENABLE         =0b1111,
            p_CHAN_BOND_SEQ_2_1              =0b0000000000,
            p_CHAN_BOND_SEQ_2_2              =0b0000000000,
            p_CHAN_BOND_SEQ_2_3              =0b0000000000,
            p_CHAN_BOND_SEQ_2_4              =0b0000000000,
            p_CHAN_BOND_SEQ_2_ENABLE         =0b1111,
            p_CHAN_BOND_SEQ_2_USE            ="FALSE",
            p_CHAN_BOND_SEQ_LEN              =1,
            p_CLK_CORRECT_USE                ="FALSE",
            p_CLK_COR_KEEP_IDLE              ="FALSE",
            p_CLK_COR_MAX_LAT                =20,
            p_CLK_COR_MIN_LAT                =18,
            p_CLK_COR_PRECEDENCE             ="TRUE",
            p_CLK_COR_REPEAT_WAIT            =0,
            p_CLK_COR_SEQ_1_1                =0b0000000000,
            p_CLK_COR_SEQ_1_2                =0b0000000000,
            p_CLK_COR_SEQ_1_3                =0b0000000000,
            p_CLK_COR_SEQ_1_4                =0b0000000000,
            p_CLK_COR_SEQ_1_ENABLE           =0b1111,
            p_CLK_COR_SEQ_2_1                =0b0000000000,
            p_CLK_COR_SEQ_2_2                =0b0000000000,
            p_CLK_COR_SEQ_2_3                =0b0000000000,
            p_CLK_COR_SEQ_2_4                =0b0000000000,
            p_CLK_COR_SEQ_2_ENABLE           =0b1111,
            p_CLK_COR_SEQ_2_USE              ="FALSE",
            p_CLK_COR_SEQ_LEN                =1,
            p_CPLL_CFG0                      =0b0110011111111000,
            p_CPLL_CFG1                      =0b1010010010101100,
            p_CPLL_CFG2                      =0b0000000000000111,
            p_CPLL_CFG3                      =0b000000,
            p_CPLL_FBDIV                     =5,
            p_CPLL_FBDIV_45                  =4,
            p_CPLL_INIT_CFG0                 =0b0000001010110010,
            p_CPLL_INIT_CFG1                 =0b00000000,
            p_CPLL_LOCK_CFG                  =0b0000000111101000,
            p_CPLL_REFCLK_DIV                =1,
            p_DDI_CTRL                       =0b00,
            p_DDI_REALIGN_WAIT               =15,
            p_DEC_MCOMMA_DETECT              ="FALSE",
            p_DEC_PCOMMA_DETECT              ="FALSE",
            p_DEC_VALID_COMMA_ONLY           ="FALSE",
            p_DFE_D_X_REL_POS                =0b0,
            p_DFE_VCM_COMP_EN                =0b0,
            p_DMONITOR_CFG0                  =0b0000000000,
            p_DMONITOR_CFG1                  =0b00000000,
            p_ES_CLK_PHASE_SEL               =0b0,
            p_ES_CONTROL                     =0b000000,
            p_ES_ERRDET_EN                   ="FALSE",
            p_ES_EYE_SCAN_EN                 ="FALSE",
            p_ES_HORZ_OFFSET                 =0b000000000000,
            p_ES_PMA_CFG                     =0b0000000000,
            p_ES_PRESCALE                    =0b00000,
            p_ES_QUALIFIER0                  =0b0000000000000000,
            p_ES_QUALIFIER1                  =0b0000000000000000,
            p_ES_QUALIFIER2                  =0b0000000000000000,
            p_ES_QUALIFIER3                  =0b0000000000000000,
            p_ES_QUALIFIER4                  =0b0000000000000000,
            p_ES_QUAL_MASK0                  =0b0000000000000000,
            p_ES_QUAL_MASK1                  =0b0000000000000000,
            p_ES_QUAL_MASK2                  =0b0000000000000000,
            p_ES_QUAL_MASK3                  =0b0000000000000000,
            p_ES_QUAL_MASK4                  =0b0000000000000000,
            p_ES_SDATA_MASK0                 =0b0000000000000000,
            p_ES_SDATA_MASK1                 =0b0000000000000000,
            p_ES_SDATA_MASK2                 =0b0000000000000000,
            p_ES_SDATA_MASK3                 =0b0000000000000000,
            p_ES_SDATA_MASK4                 =0b0000000000000000,
            p_EVODD_PHI_CFG                  =0b00000000000,
            p_EYE_SCAN_SWAP_EN               =0b0,
            p_FTS_DESKEW_SEQ_ENABLE          =0b1111,
            p_FTS_LANE_DESKEW_CFG            =0b1111,
            p_FTS_LANE_DESKEW_EN             ="FALSE",
            p_GEARBOX_MODE                   =0b00000,
            p_GM_BIAS_SELECT                 =0b0,
            p_LOCAL_MASTER                   =0b1,
            p_OOBDIVCTL                      =0b00,
            p_OOB_PWRUP                      =0b0,
            p_PCI3_AUTO_REALIGN              ="OVR_1K_BLK",
            p_PCI3_PIPE_RX_ELECIDLE          =0b0,
            p_PCI3_RX_ASYNC_EBUF_BYPASS      =0b00,
            p_PCI3_RX_ELECIDLE_EI2_ENABLE    =0b0,
            p_PCI3_RX_ELECIDLE_H2L_COUNT     =0b000000,
            p_PCI3_RX_ELECIDLE_H2L_DISABLE   =0b000,
            p_PCI3_RX_ELECIDLE_HI_COUNT      =0b000000,
            p_PCI3_RX_ELECIDLE_LP4_DISABLE   =0b0,
            p_PCI3_RX_FIFO_DISABLE           =0b0,
            p_PCIE_BUFG_DIV_CTRL             =0b0001000000000000,
            p_PCIE_RXPCS_CFG_GEN3            =0b0000001010100100,
            p_PCIE_RXPMA_CFG                 =0b0000000000001010,
            p_PCIE_TXPCS_CFG_GEN3            =0b0010010010100100,
            p_PCIE_TXPMA_CFG                 =0b0000000000001010,
            p_PCS_PCIE_EN                    ="FALSE",
            p_PCS_RSVD0                      =0b0000000000000000,
            p_PCS_RSVD1                      =0b000,
            p_PD_TRANS_TIME_FROM_P2          =0b000000111100,
            p_PD_TRANS_TIME_NONE_P2          =0b00011001,
            p_PD_TRANS_TIME_TO_P2            =0b01100100,
            p_PLL_SEL_MODE_GEN12             =0b00,
            p_PLL_SEL_MODE_GEN3              =0b11,
            p_PMA_RSV1                       =0b1111000000000000,
            p_PROCESS_PAR                    =0b010,
            p_RATE_SW_USE_DRP                =0b1,
            p_RESET_POWERSAVE_DISABLE        =0b0,
        )
        gth_params.update(
            p_RXBUFRESET_TIME                =0b00011,
            p_RXBUF_ADDR_MODE                ="FAST",
            p_RXBUF_EIDLE_HI_CNT             =0b1000,
            p_RXBUF_EIDLE_LO_CNT             =0b0000,
            p_RXBUF_EN                       ="FALSE",
            p_RXBUF_RESET_ON_CB_CHANGE       ="TRUE",
            p_RXBUF_RESET_ON_COMMAALIGN      ="FALSE",
            p_RXBUF_RESET_ON_EIDLE           ="FALSE",
            p_RXBUF_RESET_ON_RATE_CHANGE     ="TRUE",
            p_RXBUF_THRESH_OVFLW             =0,
            p_RXBUF_THRESH_OVRD              ="FALSE",
            p_RXBUF_THRESH_UNDFLW            =0,
            p_RXCDRFREQRESET_TIME            =0b00001,
            p_RXCDRPHRESET_TIME              =0b00001,
            p_RXCDR_CFG0                     =0b0000000000000000,
            p_RXCDR_CFG0_GEN3                =0b0000000000000000,
            p_RXCDR_CFG1                     =0b0000000000000000,
            p_RXCDR_CFG1_GEN3                =0b0000000000000000,
            p_RXCDR_CFG2                     =0b0000011111010110,
            p_RXCDR_CFG2_GEN3                =0b0000011111100110,
            p_RXCDR_CFG3                     =0b0000000000000000,
            p_RXCDR_CFG3_GEN3                =0b0000000000000000,
            p_RXCDR_CFG4                     =0b0000000000000000,
            p_RXCDR_CFG4_GEN3                =0b0000000000000000,
            p_RXCDR_CFG5                     =0b0000000000000000,
            p_RXCDR_CFG5_GEN3                =0b0000000000000000,
            p_RXCDR_FR_RESET_ON_EIDLE        =0b0,
            p_RXCDR_HOLD_DURING_EIDLE        =0b0,
            p_RXCDR_LOCK_CFG0                =0b0100010010000000,
            p_RXCDR_LOCK_CFG1                =0b0101111111111111,
            p_RXCDR_LOCK_CFG2                =0b0111011111000011,
            p_RXCDR_PH_RESET_ON_EIDLE        =0b0,
            p_RXCFOK_CFG0                    =0b0100000000000000,
            p_RXCFOK_CFG1                    =0b0000000001100101,
            p_RXCFOK_CFG2                    =0b0000000000101110,
            p_RXDFELPMRESET_TIME             =0b0001111,
            p_RXDFELPM_KL_CFG0               =0b0000000000000000,
            p_RXDFELPM_KL_CFG1               =0b0000000000000010,
            p_RXDFELPM_KL_CFG2               =0b0000000000000000,
            p_RXDFE_CFG0                     =0b0000101000000000,
            p_RXDFE_CFG1                     =0b0000000000000000,
            p_RXDFE_GC_CFG0                  =0b0000000000000000,
            p_RXDFE_GC_CFG1                  =0b0111100001110000,
            p_RXDFE_GC_CFG2                  =0b0000000000000000,
            p_RXDFE_H2_CFG0                  =0b0000000000000000,
            p_RXDFE_H2_CFG1                  =0b0000000000000000,
            p_RXDFE_H3_CFG0                  =0b0100000000000000,
            p_RXDFE_H3_CFG1                  =0b0000000000000000,
            p_RXDFE_H4_CFG0                  =0b0010000000000000,
            p_RXDFE_H4_CFG1                  =0b0000000000000011,
            p_RXDFE_H5_CFG0                  =0b0010000000000000,
            p_RXDFE_H5_CFG1                  =0b0000000000000011,
            p_RXDFE_H6_CFG0                  =0b0010000000000000,
            p_RXDFE_H6_CFG1                  =0b0000000000000000,
            p_RXDFE_H7_CFG0                  =0b0010000000000000,
            p_RXDFE_H7_CFG1                  =0b0000000000000000,
            p_RXDFE_H8_CFG0                  =0b0010000000000000,
            p_RXDFE_H8_CFG1                  =0b0000000000000000,
            p_RXDFE_H9_CFG0                  =0b0010000000000000,
            p_RXDFE_H9_CFG1                  =0b0000000000000000,
            p_RXDFE_HA_CFG0                  =0b0010000000000000,
            p_RXDFE_HA_CFG1                  =0b0000000000000000,
            p_RXDFE_HB_CFG0                  =0b0010000000000000,
            p_RXDFE_HB_CFG1                  =0b0000000000000000,
            p_RXDFE_HC_CFG0                  =0b0000000000000000,
            p_RXDFE_HC_CFG1                  =0b0000000000000000,
            p_RXDFE_HD_CFG0                  =0b0000000000000000,
            p_RXDFE_HD_CFG1                  =0b0000000000000000,
            p_RXDFE_HE_CFG0                  =0b0000000000000000,
            p_RXDFE_HE_CFG1                  =0b0000000000000000,
            p_RXDFE_HF_CFG0                  =0b0000000000000000,
            p_RXDFE_HF_CFG1                  =0b0000000000000000,
            p_RXDFE_OS_CFG0                  =0b1000000000000000,
            p_RXDFE_OS_CFG1                  =0b0000000000000000,
            p_RXDFE_UT_CFG0                  =0b1000000000000000,
            p_RXDFE_UT_CFG1                  =0b0000000000000011,
            p_RXDFE_VP_CFG0                  =0b1010101000000000,
            p_RXDFE_VP_CFG1                  =0b0000000000110011,
            p_RXDLY_CFG                      =0b0000000000011111,
            p_RXDLY_LCFG                     =0b0000000000110000,
            p_RXELECIDLE_CFG                 ="SIGCFG_4",
            p_RXGBOX_FIFO_INIT_RD_ADDR       =4,
            p_RXGEARBOX_EN                   ="FALSE",
            p_RXISCANRESET_TIME              =0b00001,
            p_RXLPM_CFG                      =0b0000000000000000,
            p_RXLPM_GC_CFG                   =0b0001000000000000,
            p_RXLPM_KH_CFG0                  =0b0000000000000000,
            p_RXLPM_KH_CFG1                  =0b0000000000000010,
            p_RXLPM_OS_CFG0                  =0b1000000000000000,
            p_RXLPM_OS_CFG1                  =0b0000000000000010,
            p_RXOOB_CFG                      =0b000000110,
            p_RXOOB_CLK_CFG                  ="PMA",
            p_RXOSCALRESET_TIME              =0b00011,
            p_RXOUT_DIV                      =2,
            p_RXPCSRESET_TIME                =0b00011,
            p_RXPHBEACON_CFG                 =0b0000000000000000,
            p_RXPHDLY_CFG                    =0b0010000000100000,
            p_RXPHSAMP_CFG                   =0b0010000100000000,
            p_RXPHSLIP_CFG                   =0b0110011000100010,
            p_RXPH_MONITOR_SEL               =0b00000,
            p_RXPI_CFG0                      =0b00,
            p_RXPI_CFG1                      =0b00,
            p_RXPI_CFG2                      =0b00,
            p_RXPI_CFG3                      =0b00,
            p_RXPI_CFG4                      =0b1,
            p_RXPI_CFG5                      =0b1,
            p_RXPI_CFG6                      =0b000,
            p_RXPI_LPM                       =0b0,
            p_RXPI_VREFSEL                   =0b0,
            p_RXPMACLK_SEL                   ="DATA",
            p_RXPMARESET_TIME                =0b00011,
            p_RXPRBS_ERR_LOOPBACK            =0b0,
            p_RXPRBS_LINKACQ_CNT             =15,
            p_RXSLIDE_AUTO_WAIT              =7,
            p_RXSLIDE_MODE                   ="OFF",
            p_RXSYNC_MULTILANE               =0b0,
            p_RXSYNC_OVRD                    =0b0,
            p_RXSYNC_SKIP_DA                 =0b0,
            p_RX_AFE_CM_EN                   =0b0,
            p_RX_BIAS_CFG0                   =0b0000101010110100,
            p_RX_BUFFER_CFG                  =0b000000,
            p_RX_CAPFF_SARC_ENB              =0b0,
            p_RX_CLK25_DIV                   =6,
            p_RX_CLKMUX_EN                   =0b1,
            p_RX_CLK_SLIP_OVRD               =0b00000,
            p_RX_CM_BUF_CFG                  =0b1010,
            p_RX_CM_BUF_PD                   =0b0,
            p_RX_CM_SEL                      =0b11,
            p_RX_CM_TRIM                     =0b1010,
            p_RX_CTLE3_LPF                   =0b00000001,
            p_RX_DATA_WIDTH                  =dw,
            p_RX_DDI_SEL                     =0b000000,
            p_RX_DEFER_RESET_BUF_EN          ="TRUE",
            p_RX_DFELPM_CFG0                 =0b0110,
            p_RX_DFELPM_CFG1                 =0b1,
            p_RX_DFELPM_KLKH_AGC_STUP_EN     =0b1,
            p_RX_DFE_AGC_CFG0                =0b10,
            p_RX_DFE_AGC_CFG1                =0b100,
            p_RX_DFE_KL_LPM_KH_CFG0          =0b01,
            p_RX_DFE_KL_LPM_KH_CFG1          =0b100,
            p_RX_DFE_KL_LPM_KL_CFG0          =0b01,
            p_RX_DFE_KL_LPM_KL_CFG1          =0b100,
            p_RX_DFE_LPM_HOLD_DURING_EIDLE   =0b0,
            p_RX_DISPERR_SEQ_MATCH           ="TRUE",
            p_RX_DIVRESET_TIME               =0b00001,
            p_RX_EN_HI_LR                    =0b0,
            p_RX_EYESCAN_VS_CODE             =0b0000000,
            p_RX_EYESCAN_VS_NEG_DIR          =0b0,
            p_RX_EYESCAN_VS_RANGE            =0b00,
            p_RX_EYESCAN_VS_UT_SIGN          =0b0,
            p_RX_FABINT_USRCLK_FLOP          =0b0,
            p_RX_INT_DATAWIDTH               =dw==40,
            p_RX_PMA_POWER_SAVE              =0b0,
            p_RX_PROGDIV_CFG                 =0.0,
            p_RX_SAMPLE_PERIOD               =0b111,
            p_RX_SIG_VALID_DLY               =11,
            p_RX_SUM_DFETAPREP_EN            =0b0,
            p_RX_SUM_IREF_TUNE               =0b0000,
            p_RX_SUM_RES_CTRL                =0b00,
            p_RX_SUM_VCMTUNE                 =0b0000,
            p_RX_SUM_VCM_OVWR                =0b0,
            p_RX_SUM_VREF_TUNE               =0b000,
            p_RX_TUNE_AFE_OS                 =0b10,
            p_RX_WIDEMODE_CDR                =0b0,
            p_RX_XCLK_SEL                    ="RXUSR",
            p_SAS_MAX_COM                    =64,
            p_SAS_MIN_COM                    =36,
            p_SATA_BURST_SEQ_LEN             =0b1110,
            p_SATA_CPLL_CFG                  ="VCO_3000MHZ",
            p_SATA_MAX_BURST                 =8,
            p_SATA_MAX_INIT                  =21,
            p_SATA_MAX_WAKE                  =7,
            p_SATA_MIN_BURST                 =4,
            p_SATA_MIN_INIT                  =12,
            p_SATA_MIN_WAKE                  =4,
            p_SHOW_REALIGN_COMMA             ="TRUE",
            p_SIM_RECEIVER_DETECT_PASS       ="TRUE",
            p_SIM_RESET_SPEEDUP              ="TRUE",
            p_SIM_TX_EIDLE_DRIVE_LEVEL       =0b0,
            p_SIM_VERSION                    =2,
            p_TAPDLY_SET_TX                  =0b00,
            p_TEMPERATUR_PAR                 =0b0010,
            p_TERM_RCAL_CFG                  =0b100001000010000,
            p_TERM_RCAL_OVRD                 =0b000,
            p_TRANS_TIME_RATE                =0b00001110,
            p_TST_RSV0                       =0b00000000,
            p_TST_RSV1                       =0b00000000,
        )
        gth_params.update(
            p_TXBUF_EN                       ="FALSE",
            p_TXBUF_RESET_ON_RATE_CHANGE     ="TRUE",
            p_TXDLY_CFG                      =0b0000000000001001,
            p_TXDLY_LCFG                     =0b0000000001010000,
            p_TXDRVBIAS_N                    =0b1010,
            p_TXDRVBIAS_P                    =0b1010,
            p_TXFIFO_ADDR_CFG                ="LOW",
            p_TXGBOX_FIFO_INIT_RD_ADDR       =4,
            p_TXGEARBOX_EN                   ="FALSE",
            p_TXOUT_DIV                      =2,
            p_TXPCSRESET_TIME                =0b00011,
            p_TXPHDLY_CFG0                   =0b0010000000100000,
            p_TXPHDLY_CFG1                   =0b0000000001110101,
            p_TXPH_CFG                       =0b0000100110000000,
            p_TXPH_MONITOR_SEL               =0b00000,
            p_TXPI_CFG0                      =0b00,
            p_TXPI_CFG1                      =0b00,
            p_TXPI_CFG2                      =0b00,
            p_TXPI_CFG3                      =0b1,
            p_TXPI_CFG4                      =0b1,
            p_TXPI_CFG5                      =0b000,
            p_TXPI_GRAY_SEL                  =0b0,
            p_TXPI_INVSTROBE_SEL             =0b0,
            p_TXPI_LPM                       =0b0,
            p_TXPI_PPMCLK_SEL                ="TXUSRCLK2",
            p_TXPI_PPM_CFG                   =0b00000000,
            p_TXPI_SYNFREQ_PPM               =0b001,
            p_TXPI_VREFSEL                   =0b0,
            p_TXPMARESET_TIME                =0b00011,
            p_TXSYNC_MULTILANE               =0 if mode == "single" else 1,
            p_TXSYNC_OVRD                    =0b0,
            p_TXSYNC_SKIP_DA                 =0b0,
            p_TX_CLK25_DIV                   =6,
            p_TX_CLKMUX_EN                   =0b1,
            p_TX_DATA_WIDTH                  =dw,
            p_TX_DCD_CFG                     =0b000010,
            p_TX_DCD_EN                      =0b0,
            p_TX_DEEMPH0                     =0b000000,
            p_TX_DEEMPH1                     =0b000000,
            p_TX_DIVRESET_TIME               =0b00001,
            p_TX_DRIVE_MODE                  ="DIRECT",
            p_TX_EIDLE_ASSERT_DELAY          =0b100,
            p_TX_EIDLE_DEASSERT_DELAY        =0b011,
            p_TX_EML_PHI_TUNE                =0b0,
            p_TX_FABINT_USRCLK_FLOP          =0b0,
            p_TX_IDLE_DATA_ZERO              =0b0,
            p_TX_INT_DATAWIDTH               =dw==40,
            p_TX_LOOPBACK_DRIVE_HIZ          ="FALSE",
            p_TX_MAINCURSOR_SEL              =0b0,
            p_TX_MARGIN_FULL_0               =0b1001111,
            p_TX_MARGIN_FULL_1               =0b1001110,
            p_TX_MARGIN_FULL_2               =0b1001100,
            p_TX_MARGIN_FULL_3               =0b1001010,
            p_TX_MARGIN_FULL_4               =0b1001000,
            p_TX_MARGIN_LOW_0                =0b1000110,
            p_TX_MARGIN_LOW_1                =0b1000101,
            p_TX_MARGIN_LOW_2                =0b1000011,
            p_TX_MARGIN_LOW_3                =0b1000010,
            p_TX_MARGIN_LOW_4                =0b1000000,
            p_TX_MODE_SEL                    =0b000,
            p_TX_PMADATA_OPT                 =0b0,
            p_TX_PMA_POWER_SAVE              =0b0,
            p_TX_PROGCLK_SEL                 ="PREPI",
            p_TX_PROGDIV_CFG                 =dw/rtiox_mul,
            p_TX_QPI_STATUS_EN               =0b0,
            p_TX_RXDETECT_CFG                =0b00000000110010,
            p_TX_RXDETECT_REF                =0b100,
            p_TX_SAMPLE_PERIOD               =0b111,
            p_TX_SARC_LPBK_ENB               =0b0,
            p_TX_XCLK_SEL                    ="TXUSR",
            p_USE_PCS_CLK_PHASE_SEL          =0b0,
            p_WB_MODE                        =0b00,
        )
        gth_params.update(
            # Reset modes
            i_GTRESETSEL=0,
            i_RESETOVRD=0,
          
            i_CPLLRESET=0,
            i_CPLLPD=cpll_reset,
            o_CPLLLOCK=cpll_lock,
            i_CPLLLOCKEN=1,
            i_CPLLREFCLKSEL=0b001,
            i_TSTIN=2**20-1,
            i_GTREFCLK0=refclk,

            # TX clock
           
            o_TXOUTCLK=self.txoutclk,
            i_TXSYSCLKSEL=0b00,
            i_TXPLLCLKSEL=0b00,
            i_TXOUTCLKSEL=0b101,

            # TX Startup/Reset
            i_GTTXRESET=tx_init.gtXxreset,
            o_TXRESETDONE=tx_init.Xxresetdone,
            i_TXDLYSRESET=tx_init.Xxdlysreset if mode != "slave" else self.txdlysreset,
            o_TXDLYSRESETDONE=tx_init.Xxdlysresetdone,
            o_TXPHALIGNDONE=tx_init.Xxphaligndone,
            i_TXUSERRDY=tx_init.Xxuserrdy,
            i_TXSYNCMODE=mode != "slave",
          
            i_TXSYNCALLIN=self.txsyncallin,
            i_TXSYNCIN=self.txsyncin,
            o_TXSYNCOUT=self.txsyncout,

            # TX data

            i_TXCTRL0=Cat(*[txdata[10*i+8] for i in range(nwords)]),
            i_TXCTRL1=Cat(*[txdata[10*i+9] for i in range(nwords)]),
            i_TXDATA=Cat(*[txdata[10*i:10*i+8] for i in range(nwords)]),
            i_TXUSRCLK=ClockSignal("rtio_tx"),
            i_TXUSRCLK2=ClockSignal("rtio_tx"),

            # TX electrical
            i_TXPD=0b00,
            i_TXBUFDIFFCTRL=0b000,
            i_TXDIFFCTRL=0b1100,

            # RX Startup/Reset
            i_GTRXRESET=rx_init.gtXxreset,
            o_RXRESETDONE=rx_init.Xxresetdone,
            i_RXDLYSRESET=rx_init.Xxdlysreset,
            o_RXPHALIGNDONE=rxphaligndone,
            i_RXSYNCALLIN=rxphaligndone,
            i_RXUSERRDY=rx_init.Xxuserrdy,
            i_RXSYNCIN=0,
            i_RXSYNCMODE=1,
            o_RXSYNCDONE=rx_init.Xxsyncdone,

            # RX AFE
            i_RXDFEAGCCTRL=1,
            i_RXDFEXYDEN=1,
            i_RXLPMEN=1,
            i_RXOSINTCFG=0xd,
            i_RXOSINTEN=1,

            # RX clock
            i_RXRATE=0,
            i_RXDLYBYPASS=0,        
            i_RXSYSCLKSEL=0b00,
            i_RXOUTCLKSEL=0b010,
            i_RXPLLCLKSEL=0b00,
            o_RXRECCLKOUT=self.rxrecclkout,
            o_RXOUTCLK=self.rxoutclk,
            i_RXUSRCLK=ClockSignal("rtio_rx"),
            i_RXUSRCLK2=ClockSignal("rtio_rx"),

            # RX data
            o_RXCTRL0=Cat(*[rxdata[10*i+8] for i in range(nwords)]),
            o_RXCTRL1=Cat(*[rxdata[10*i+9] for i in range(nwords)]),
            o_RXDATA=Cat(*[rxdata[10*i:10*i+8] for i in range(nwords)]),

            # RX electrical
            i_RXPD=Replicate(rx_init.restart, 2),
			i_RXELECIDLEMODE=0b11,

            # Pads
            i_GTHRXP=pads.rxp,
            i_GTHRXN=pads.rxn,
            o_GTHTXP=pads.txp,
            o_GTHTXN=pads.txn
        )
        self.specials += Instance("GTHE3_CHANNEL", **gth_params)
        self.comb += self.txphaligndone.eq(tx_init.Xxphaligndone)

        self.submodules += [
            add_probe_async("drtio_gth", "cpll_lock", cpll_lock),
            add_probe_async("drtio_gth", "txuserrdy", tx_init.Xxuserrdy),
            add_probe_async("drtio_gth", "tx_init_done", tx_init.done),
            add_probe_async("drtio_gth", "rxuserrdy", rx_init.Xxuserrdy),
            add_probe_async("drtio_gth", "rx_init_done", rx_init.done),
            add_probe_buffer("drtio_gth", "txdata", txdata, clock_domain="rtio_tx"),
            add_probe_buffer("drtio_gth", "rxdata", rxdata, clock_domain="rtio_rx")
        ]

        # tx clocking
        tx_reset_deglitched = Signal()
        tx_reset_deglitched.attr.add("no_retiming")
        self.sync += tx_reset_deglitched.eq(~tx_init.done)
        self.clock_domains.cd_rtio_tx = ClockDomain()
        self.clock_domains.cd_rtiox_tx = ClockDomain()
        if mode == "master" or mode == "single":
            self.specials += [
                Instance("BUFG_GT", i_I=self.txoutclk, o_O=self.cd_rtiox_tx.clk, i_DIV=0),
                Instance("BUFG_GT", i_I=self.txoutclk, o_O=self.cd_rtio_tx.clk, i_DIV=rtiox_mul-1)
            ]
        self.specials += AsyncResetSynchronizer(self.cd_rtio_tx, tx_reset_deglitched)

        # rx clocking
        rx_reset_deglitched = Signal()
        rx_reset_deglitched.attr.add("no_retiming")
        self.sync.rtio_tx += rx_reset_deglitched.eq(~rx_init.done)
        self.clock_domains.cd_rtio_rx = ClockDomain()
        self.specials += [
            Instance("BUFG_GT", i_I=self.rxoutclk, o_O=self.cd_rtio_rx.clk),
            AsyncResetSynchronizer(self.cd_rtio_rx, rx_reset_deglitched)
        ]

        # tx data
        self.comb += txdata.eq(Cat(*[encoder.output[i] for i in range(nwords)]))

        # rx data
        for i in range(nwords):
            self.comb += decoders[i].input.eq(rxdata[10*i:10*(i+1)])

        # clock alignment
        clock_aligner = BruteforceClockAligner(0b0101111100, rtio_clk_freq)
        self.submodules += clock_aligner
        self.comb += [
            clock_aligner.rxdata.eq(rxdata),
            rx_init.restart.eq(clock_aligner.restart),
            self.rx_ready.eq(clock_aligner.ready)
        ]
        self.submodules += add_probe_async("drtio_gth", "clock_aligner_ready", clock_aligner.ready)


class GTHTXPhaseAlignement(Module):
    # TX Buffer Bypass in  Single-Lane/Multi-Lane Auto Mode (ug576)
    def __init__(self, gths):
        txsyncallin = Signal()
        txsync = Signal()
        txphaligndone = Signal(len(gths))
        txdlysreset = Signal()
        ready_for_align = Signal(len(gths))
        all_ready_for_align = Signal()

        for i, gth in enumerate(gths):
            # Common to all transceivers
            self.comb += [
                ready_for_align[i].eq(1),
                gth.txsyncin.eq(txsync),
                gth.txsyncallin.eq(txsyncallin),
                txphaligndone[i].eq(gth.txphaligndone)
            ]
            # Specific to Master or Single transceivers
            if gth.mode == "master" or gth.mode == "single":
                self.comb += [
                    gth.tx_init.all_ready_for_align.eq(all_ready_for_align),
                    txsync.eq(gth.txsyncout),
                    txdlysreset.eq(gth.tx_init.Xxdlysreset)
                ]
            # Specific to Slave transceivers
            else:
                self.comb += [
                    ready_for_align[i].eq(gth.tx_init.ready_for_align),
                    gth.txdlysreset.eq(txdlysreset),
                ]

        self.comb += [
            txsyncallin.eq(reduce(and_, [txphaligndone[i] for i in range(len(gths))])),
            all_ready_for_align.eq(reduce(and_, [ready_for_align[i] for i in range(len(gths))]))
        ]


class GTH(Module, TransceiverInterface):
    def __init__(self, clock_pads, data_pads, sys_clk_freq, rtio_clk_freq, rtiox_mul=2, dw=20, master=0, clock_recout_pads=None):
        self.nchannels = nchannels = len(data_pads)
        self.gths = []

        # # #

        create_buf = hasattr(clock_pads, "p")
        if create_buf:
            refclk = Signal()
            ibufds_ceb = Signal()
            self.specials += Instance("IBUFDS_GTE3",
                i_CEB=ibufds_ceb,
                i_I=clock_pads.p,
                i_IB=clock_pads.n,
                o_O=refclk)
        else:
            refclk = clock_pads

        rtio_tx_clk = Signal()
        channel_interfaces = []
        for i in range(nchannels):
            if nchannels == 1:
                mode = "single"
            else:
                mode = "master" if i == master else "slave"
            gth = GTHSingle(refclk, data_pads[i], sys_clk_freq, rtio_clk_freq, rtiox_mul, dw, mode)
            if mode == "master":
                self.comb += rtio_tx_clk.eq(gth.cd_rtio_tx.clk)
            elif mode == "slave":
                self.comb += gth.cd_rtio_tx.clk.eq(rtio_tx_clk)
            self.gths.append(gth)
            setattr(self.submodules, "gth"+str(i), gth)
            channel_interface = ChannelInterface(gth.encoder, gth.decoders)
            self.comb += channel_interface.rx_ready.eq(gth.rx_ready)
            channel_interfaces.append(channel_interface)

        self.submodules.tx_phase_alignment = GTHTXPhaseAlignement(self.gths)

        TransceiverInterface.__init__(self, channel_interfaces)
        self.clock_domains.cd_rtiox = ClockDomain(reset_less=True)
        if create_buf:
            # GTH PLLs recover on their own from an interrupted clock input,
            # but be paranoid about HMC7043 noise.
            self.stable_clkin.storage.attr.add("no_retiming")
            self.comb += ibufds_ceb.eq(~self.stable_clkin.storage)

        self.comb += [
            self.cd_rtio.clk.eq(self.gths[master].cd_rtio_tx.clk),
            self.cd_rtiox.clk.eq(self.gths[master].cd_rtiox_tx.clk),
            self.cd_rtio.rst.eq(reduce(or_, [gth.cd_rtio_tx.rst for gth in self.gths]))
        ]
        for i in range(nchannels):
            self.comb += [
                getattr(self, "cd_rtio_rx" + str(i)).clk.eq(self.gths[i].cd_rtio_rx.clk),
                getattr(self, "cd_rtio_rx" + str(i)).rst.eq(self.gths[i].cd_rtio_rx.rst)
            ]

        if clock_recout_pads is not None:
            self.specials += Instance("OBUFDS_GTE3",
                p_REFCLK_EN_TX_PATH=0b1,
                p_REFCLK_ICNTL_TX=0b00111,
                i_I=self.gths[0].rxrecclkout,
                i_CEB=0,
                o_O=clock_recout_pads.p, o_OB=clock_recout_pads.n)
