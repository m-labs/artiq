from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from misoc.cores.code_8b10b import Encoder, Decoder
from misoc.interconnect.csr import *

from artiq.gateware.drtio.core import TransceiverInterface, ChannelInterface
from artiq.gateware.drtio.transceiver.clock_aligner import BruteforceClockAligner
from artiq.gateware.drtio.transceiver.gtx_7series_init import *


class GTX_20X(Module, TransceiverInterface):
    # Settings:
    # * GTX reference clock (at clock_pads) @ 125MHz == coarse RTIO frequency
    # * GTX data width = 20
    # * GTX PLL frequency @ 2.5GHz
    # * GTX line rate (TX & RX) @ 2.5Gb/s
    # * GTX TX/RX USRCLK @ 125MHz == coarse RTIO frequency
    def __init__(self, clock_pads, tx_pads, rx_pads, sys_clk_freq):
        encoder = ClockDomainsRenamer("rtio")(
            Encoder(2, True))
        self.submodules += encoder
        decoders = [ClockDomainsRenamer("rtio_rx0")(
            (Decoder(True))) for _ in range(2)]
        self.submodules += decoders

        TransceiverInterface.__init__(self, [ChannelInterface(encoder, decoders)])

        # transceiver direct clock outputs
        # useful to specify clock constraints in a way palatable to Vivado
        self.txoutclk = Signal()
        self.rxoutclk = Signal()

        # # #

        refclk = Signal()
        stable_clkin_n = Signal()
        self.stable_clkin.storage.attr.add("no_retiming")
        self.comb += stable_clkin_n.eq(~self.stable_clkin.storage)
        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=stable_clkin_n,
            i_I=clock_pads.p,
            i_IB=clock_pads.n,
            o_O=refclk
        )

        cpllreset = Signal()
        cplllock = Signal()
        # TX generates RTIO clock, init must be in system domain
        tx_init = GTXInit(sys_clk_freq, False)
        # RX receives restart commands from RTIO domain
        rx_init = ClockDomainsRenamer("rtio")(
            GTXInit(self.rtio_clk_freq, True))
        self.submodules += tx_init, rx_init
        self.comb += [
            cpllreset.eq(tx_init.cpllreset),
            tx_init.cplllock.eq(cplllock),
            rx_init.cplllock.eq(cplllock)
        ]

        txdata = Signal(20)
        rxdata = Signal(20)
        self.specials += \
            Instance("GTXE2_CHANNEL",
                # PMA Attributes
                p_PMA_RSV=0x00018480,
                p_PMA_RSV2=0x2050,              # PMA_RSV2[5] = 0: Eye scan feature disabled
                p_PMA_RSV3=0,
                p_PMA_RSV4=1,                   # PMA_RSV[4],RX_CM_TRIM[2:0] = 0b1010: Common mode 800mV
                p_RX_BIAS_CFG=0b000000000100,
                p_RX_OS_CFG=0b0000010000000,
                p_RX_CLK25_DIV=5,
                p_TX_CLK25_DIV=5,

                # Power-Down Attributes
                p_PD_TRANS_TIME_FROM_P2=0x3c,
                p_PD_TRANS_TIME_NONE_P2=0x3c,
                p_PD_TRANS_TIME_TO_P2=0x64,

                # CPLL
                p_CPLL_CFG=0xBC07DC,
                p_CPLL_FBDIV=4,
                p_CPLL_FBDIV_45=5,
                p_CPLL_REFCLK_DIV=1,
                p_RXOUT_DIV=2,
                p_TXOUT_DIV=2,
                i_CPLLRESET=cpllreset,
                i_CPLLPD=cpllreset,
                o_CPLLLOCK=cplllock,
                i_CPLLLOCKEN=1,
                i_CPLLREFCLKSEL=0b001,
                i_TSTIN=2**20-1,
                i_GTREFCLK0=refclk,

                # TX clock
                p_TXBUF_EN="FALSE",
                p_TX_XCLK_SEL="TXUSR",
                o_TXOUTCLK=self.txoutclk,
                i_TXSYSCLKSEL=0b00,
                i_TXOUTCLKSEL=0b11,

                # TX Startup/Reset
                i_GTTXRESET=tx_init.gtXxreset,
                o_TXRESETDONE=tx_init.Xxresetdone,
                i_TXDLYSRESET=tx_init.Xxdlysreset,
                o_TXDLYSRESETDONE=tx_init.Xxdlysresetdone,
                o_TXPHALIGNDONE=tx_init.Xxphaligndone,
                i_TXUSERRDY=tx_init.Xxuserrdy,
                p_TXPMARESET_TIME=1,
                p_TXPCSRESET_TIME=1,
                i_TXINHIBIT=~self.txenable.storage,

                # TX data
                p_TX_DATA_WIDTH=20,
                p_TX_INT_DATAWIDTH=0,
                i_TXCHARDISPMODE=Cat(txdata[9], txdata[19]),
                i_TXCHARDISPVAL=Cat(txdata[8], txdata[18]),
                i_TXDATA=Cat(txdata[:8], txdata[10:18]),
                i_TXUSRCLK=ClockSignal("rtio"),
                i_TXUSRCLK2=ClockSignal("rtio"),

                # TX electrical
                i_TXBUFDIFFCTRL=0b100,
                i_TXDIFFCTRL=0b1000,

                # RX Startup/Reset
                i_GTRXRESET=rx_init.gtXxreset,
                o_RXRESETDONE=rx_init.Xxresetdone,
                i_RXDLYSRESET=rx_init.Xxdlysreset,
                o_RXDLYSRESETDONE=rx_init.Xxdlysresetdone,
                o_RXPHALIGNDONE=rx_init.Xxphaligndone,
                i_RXUSERRDY=rx_init.Xxuserrdy,
                p_RXPMARESET_TIME=1,
                p_RXPCSRESET_TIME=1,

                # RX AFE
                p_RX_DFE_XYD_CFG=0,
                p_RX_CM_SEL=0b11,               # RX_CM_SEL = 0b11: Common mode is programmable
                p_RX_CM_TRIM=0b010,             # PMA_RSV[4],RX_CM_TRIM[2:0] = 0b1010: Common mode 800mV
                i_RXDFEXYDEN=1,
                i_RXDFEXYDHOLD=0,
                i_RXDFEXYDOVRDEN=0,
                i_RXLPMEN=0,                    # RXLPMEN = 0: DFE mode is enabled
                p_RX_DFE_GAIN_CFG=0x0207EA,
                p_RX_DFE_VP_CFG=0b00011111100000011,
                p_RX_DFE_UT_CFG=0b10001000000000000,
                p_RX_DFE_KL_CFG=0b0000011111110,
                p_RX_DFE_KL_CFG2=0x3788140A,
                p_RX_DFE_H2_CFG=0b000110000000,
                p_RX_DFE_H3_CFG=0b000110000000,
                p_RX_DFE_H4_CFG=0b00011100000,
                p_RX_DFE_H5_CFG=0b00011100000,
                p_RX_DFE_LPM_CFG=0x0904,        # RX_DFE_LPM_CFG = 0x0904: linerate <= 6.6Gb/s
                                                #                = 0x0104: linerate > 6.6Gb/s

                # RX clock
                i_RXDDIEN=1,
                i_RXSYSCLKSEL=0b00,
                i_RXOUTCLKSEL=0b010,
                o_RXOUTCLK=self.rxoutclk,
                i_RXUSRCLK=ClockSignal("rtio_rx0"),
                i_RXUSRCLK2=ClockSignal("rtio_rx0"),

                # RX Clock Correction Attributes
                p_CLK_CORRECT_USE="FALSE",
                p_CLK_COR_SEQ_1_1=0b0100000000,
                p_CLK_COR_SEQ_2_1=0b0100000000,
                p_CLK_COR_SEQ_1_ENABLE=0b1111,
                p_CLK_COR_SEQ_2_ENABLE=0b1111,

                # RX data
                p_RX_DATA_WIDTH=20,
                p_RX_INT_DATAWIDTH=0,
                o_RXDISPERR=Cat(rxdata[9], rxdata[19]),
                o_RXCHARISK=Cat(rxdata[8], rxdata[18]),
                o_RXDATA=Cat(rxdata[:8], rxdata[10:18]),

                # RX Byte and Word Alignment Attributes
                p_ALIGN_COMMA_DOUBLE="FALSE",
                p_ALIGN_COMMA_ENABLE=0b1111111111,
                p_ALIGN_COMMA_WORD=1,
                p_ALIGN_MCOMMA_DET="TRUE",
                p_ALIGN_MCOMMA_VALUE=0b1010000011,
                p_ALIGN_PCOMMA_DET="TRUE",
                p_ALIGN_PCOMMA_VALUE=0b0101111100,
                p_SHOW_REALIGN_COMMA="FALSE",
                p_RXSLIDE_AUTO_WAIT=7,
                p_RXSLIDE_MODE="PCS",
                p_RX_SIG_VALID_DLY=10,

                # RX 8B/10B Decoder Attributes
                p_RX_DISPERR_SEQ_MATCH="FALSE",
                p_DEC_MCOMMA_DETECT="TRUE",
                p_DEC_PCOMMA_DETECT="TRUE",
                p_DEC_VALID_COMMA_ONLY="FALSE",

                # RX Buffer Attributes
                p_RXBUF_ADDR_MODE="FAST",
                p_RXBUF_EIDLE_HI_CNT=0b1000,
                p_RXBUF_EIDLE_LO_CNT=0b0000,
                p_RXBUF_EN="FALSE",
                p_RX_BUFFER_CFG=0b000000,
                p_RXBUF_RESET_ON_CB_CHANGE="TRUE",
                p_RXBUF_RESET_ON_COMMAALIGN="FALSE",
                p_RXBUF_RESET_ON_EIDLE="FALSE",     # RXBUF_RESET_ON_EIDLE = FALSE: OOB is disabled
                p_RXBUF_RESET_ON_RATE_CHANGE="TRUE",
                p_RXBUFRESET_TIME=0b00001,
                p_RXBUF_THRESH_OVFLW=61,
                p_RXBUF_THRESH_OVRD="FALSE",
                p_RXBUF_THRESH_UNDFLW=4,
                p_RXDLY_CFG=0x001F,
                p_RXDLY_LCFG=0x030,
                p_RXDLY_TAP_CFG=0x0000,
                p_RXPH_CFG=0xC00002,
                p_RXPHDLY_CFG=0x084020,
                p_RXPH_MONITOR_SEL=0b00000,
                p_RX_XCLK_SEL="RXUSR",
                p_RX_DDI_SEL=0b000000,
                p_RX_DEFER_RESET_BUF_EN="TRUE",

                # CDR Attributes
                p_RXCDR_CFG=0x03000023FF20400020,   # DFE @ <= 6.6Gb/s, scrambled, CDR setting < +/- 200ppm
                                                    # (See UG476 (v1.12.1), p.206)
                p_RXCDR_FR_RESET_ON_EIDLE=0b0,
                p_RXCDR_HOLD_DURING_EIDLE=0b0,
                p_RXCDR_PH_RESET_ON_EIDLE=0b0,
                p_RXCDR_LOCK_CFG=0b010101,

                # # RX Initialization and Reset Attributes
                # p_RXCDRFREQRESET_TIME=0b00001,
                # p_RXCDRPHRESET_TIME=0b00001,
                # p_RXISCANRESET_TIME=0b00001,
                # p_RXPCSRESET_TIME=0b00001,
                # p_RXPMARESET_TIME=0b00011,

                # Pads
                i_GTXRXP=rx_pads.p,
                i_GTXRXN=rx_pads.n,
                o_GTXTXP=tx_pads.p,
                o_GTXTXN=tx_pads.n,

                # Other parameters
                p_PCS_RSVD_ATTR=0x000,              # PCS_RSVD_ATTR[1] = 0: TX Single Lane Auto Mode
                                                    #              [2] = 0: RX Single Lane Auto Mode
                                                    #              [8] = 0: OOB is disabled
                i_RXELECIDLEMODE=0b11,              # RXELECIDLEMODE = 0b11: OOB is disabled
                p_RX_DFE_LPM_HOLD_DURING_EIDLE=0b0,
                p_ES_EYE_SCAN_EN="TRUE",            # Must be TRUE for GTX
            )

        tx_reset_deglitched = Signal()
        tx_reset_deglitched.attr.add("no_retiming")
        self.sync += tx_reset_deglitched.eq(~tx_init.done)
        self.specials += [
            Instance("BUFG", i_I=self.txoutclk, o_O=self.cd_rtio.clk),
            AsyncResetSynchronizer(self.cd_rtio, tx_reset_deglitched)
        ]
        rx_reset_deglitched = Signal()
        rx_reset_deglitched.attr.add("no_retiming")
        self.sync.rtio += rx_reset_deglitched.eq(~rx_init.done)
        self.specials += [
            Instance("BUFG", i_I=self.rxoutclk, o_O=self.cd_rtio_rx0.clk),
            AsyncResetSynchronizer(self.cd_rtio_rx0, rx_reset_deglitched)
        ]

        chan = self.channels[0]
        self.comb += [
            txdata.eq(Cat(chan.encoder.output[0], chan.encoder.output[1])),
            chan.decoders[0].input.eq(rxdata[:10]),
            chan.decoders[1].input.eq(rxdata[10:])
        ]

        clock_aligner = ClockDomainsRenamer({"rtio_rx": "rtio_rx0"})(
            BruteforceClockAligner(0b0101111100, self.rtio_clk_freq))
        self.submodules += clock_aligner
        self.comb += [
            clock_aligner.rxdata.eq(rxdata),
            rx_init.restart.eq(clock_aligner.restart),
            chan.rx_ready.eq(clock_aligner.ready)
        ]


class GTX_1000BASE_BX10(GTX_20X):
    rtio_clk_freq = 125e6


class RXSynchronizer(Module, AutoCSR):
    """Delays the data received in the rtio_rx domain by a configurable amount
    so that it meets s/h in the rtio domain, and recapture it in the rtio
    domain. This has fixed latency.

    Since Xilinx doesn't provide decent on-chip delay lines, we implement the
    delay with MMCM that provides a clock and a finely configurable phase, used
    to resample the data.

    The phase has to be determined either empirically or by making sense of the
    Xilinx scriptures (when existent) and should be constant for a given design
    placement.
    """
    def __init__(self, rtio_clk_freq, initial_phase=0.0):
        self.phase_shift = CSR()
        self.phase_shift_done = CSRStatus()

        self.clock_domains.cd_rtio_delayed = ClockDomain()

        mmcm_output = Signal()
        mmcm_fb = Signal()
        mmcm_locked = Signal()
        # maximize VCO frequency to maximize phase shift resolution
        mmcm_mult = 1200e6//rtio_clk_freq
        self.specials += [
            Instance("MMCME2_ADV",
                p_CLKIN1_PERIOD=1e9/rtio_clk_freq,
                i_CLKIN1=ClockSignal("rtio_rx"),
                i_RST=ResetSignal("rtio_rx"),
                i_CLKINSEL=1,  # yes, 1=CLKIN1 0=CLKIN2

                p_CLKFBOUT_MULT_F=mmcm_mult,
                p_CLKOUT0_DIVIDE_F=mmcm_mult,
                p_CLKOUT0_PHASE=initial_phase,
                p_DIVCLK_DIVIDE=1,

                # According to Xilinx, there is no guarantee of input/output
                # phase relationship when using internal feedback. We assume
                # here that the input/ouput skew is constant to save BUFGs.
                o_CLKFBOUT=mmcm_fb,
                i_CLKFBIN=mmcm_fb,

                p_CLKOUT0_USE_FINE_PS="TRUE",
                o_CLKOUT0=mmcm_output,
                o_LOCKED=mmcm_locked,

                i_PSCLK=ClockSignal(),
                i_PSEN=self.phase_shift.re,
                i_PSINCDEC=self.phase_shift.r,
                o_PSDONE=self.phase_shift_done.status,
            ),
            Instance("BUFR", i_I=mmcm_output, o_O=self.cd_rtio_delayed.clk),
            AsyncResetSynchronizer(self.cd_rtio_delayed, ~mmcm_locked)
        ]

    def resync(self, signal):
        delayed = Signal.like(signal, related=signal)
        synchronized = Signal.like(signal, related=signal)
        self.sync.rtio_delayed += delayed.eq(signal)
        self.sync.rtio += synchronized.eq(delayed)
        return synchronized
