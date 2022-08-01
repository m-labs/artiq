from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from misoc.cores.code_8b10b import Encoder, Decoder
from misoc.interconnect.csr import *

from artiq.gateware.drtio.core import TransceiverInterface, ChannelInterface
from artiq.gateware.drtio.transceiver.clock_aligner import BruteforceClockAligner
from artiq.gateware.drtio.transceiver.gtx_7series_init import *


class GTX_20X(Module):
    # Settings:
    # * GTX reference clock @ 125MHz == coarse RTIO frequency
    # * GTX data width = 20
    # * GTX PLL frequency @ 2.5GHz
    # * GTX line rate (TX & RX) @ 2.5Gb/s
    # * GTX TX/RX USRCLK @ 125MHz == coarse RTIO frequency
    def __init__(self, refclk, pads, sys_clk_freq, rtio_clk_freq=125e6, tx_mode="single", rx_mode="single"):
        assert tx_mode in ["single", "master", "slave"]
        assert rx_mode in ["single", "master", "slave"]

        self.txenable = Signal()
        self.submodules.encoder = ClockDomainsRenamer("rtio_tx")(
            Encoder(2, True))
        self.submodules.decoders = [ClockDomainsRenamer("rtio_rx")(
            (Decoder(True))) for _ in range(2)]
        self.rx_ready = Signal()

        # transceiver direct clock outputs
        # useful to specify clock constraints in a way palatable to Vivado
        self.txoutclk = Signal()
        self.rxoutclk = Signal()

        # # #

        cpllreset = Signal()
        cplllock = Signal()
        # TX generates RTIO clock, init must be in system domain
        self.submodules.tx_init = tx_init = GTXInit(sys_clk_freq, False, mode=tx_mode)
        # RX receives restart commands from RTIO domain
        self.submodules.rx_init = rx_init = ClockDomainsRenamer("rtio_tx")(
            GTXInit(rtio_clk_freq, True, mode=rx_mode))
        self.comb += [
            cpllreset.eq(tx_init.cpllreset),
            tx_init.cplllock.eq(cplllock),
            rx_init.cplllock.eq(cplllock)
        ]

        txdata = Signal(20)
        rxdata = Signal(20)
        # Note: the following parameters were set after consulting AR45360
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
                i_TXPHDLYRESET=0,
                i_TXDLYBYPASS=0,
                i_TXPHALIGNEN=1 if tx_mode != "single" else 0,
                i_GTTXRESET=tx_init.gtXxreset,
                o_TXRESETDONE=tx_init.Xxresetdone,
                i_TXDLYSRESET=tx_init.Xxdlysreset,
                o_TXDLYSRESETDONE=tx_init.Xxdlysresetdone,
                i_TXPHINIT=tx_init.txphinit if tx_mode != "single" else 0,
                o_TXPHINITDONE=tx_init.txphinitdone if tx_mode != "single" else Signal(),
                i_TXPHALIGN=tx_init.Xxphalign if tx_mode != "single" else 0,
                i_TXDLYEN=tx_init.Xxdlyen if tx_mode != "single" else 0,
                o_TXPHALIGNDONE=tx_init.Xxphaligndone,
                i_TXUSERRDY=tx_init.Xxuserrdy,
                p_TXPMARESET_TIME=1,
                p_TXPCSRESET_TIME=1,
                i_TXINHIBIT=~self.txenable,

                # TX data
                p_TX_DATA_WIDTH=20,
                p_TX_INT_DATAWIDTH=0,
                i_TXCHARDISPMODE=Cat(txdata[9], txdata[19]),
                i_TXCHARDISPVAL=Cat(txdata[8], txdata[18]),
                i_TXDATA=Cat(txdata[:8], txdata[10:18]),
                i_TXUSRCLK=ClockSignal("rtio_tx"),
                i_TXUSRCLK2=ClockSignal("rtio_tx"),

                # TX electrical
                i_TXBUFDIFFCTRL=0b100,
                i_TXDIFFCTRL=0b1000,

                # RX Startup/Reset
                i_RXPHDLYRESET=0,
                i_RXDLYBYPASS=0,
                i_RXPHALIGNEN=1 if rx_mode != "single" else 0,
                i_GTRXRESET=rx_init.gtXxreset,
                o_RXRESETDONE=rx_init.Xxresetdone,
                i_RXDLYSRESET=rx_init.Xxdlysreset,
                o_RXDLYSRESETDONE=rx_init.Xxdlysresetdone,
                i_RXPHALIGN=rx_init.Xxphalign if rx_mode != "single" else 0,
                i_RXDLYEN=rx_init.Xxdlyen if rx_mode != "single" else 0,
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
                i_RXUSRCLK=ClockSignal("rtio_rx"),
                i_RXUSRCLK2=ClockSignal("rtio_rx"),

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

                # Pads
                i_GTXRXP=pads.rxp,
                i_GTXRXN=pads.rxn,
                o_GTXTXP=pads.txp,
                o_GTXTXN=pads.txn,

                # Other parameters
                p_PCS_RSVD_ATTR=(
                    (tx_mode != "single") << 1 |    # PCS_RSVD_ATTR[1] = 0: TX Single Lane Auto Mode
                                                    #                  = 1: TX Manual Mode
                    (rx_mode != "single") << 2 |    #              [2] = 0: RX Single Lane Auto Mode
                                                    #                  = 1: RX Manual Mode
                    0 << 8                          #              [8] = 0: OOB is disabled
                ),
                i_RXELECIDLEMODE=0b11,              # RXELECIDLEMODE = 0b11: OOB is disabled
                p_RX_DFE_LPM_HOLD_DURING_EIDLE=0b0,
                p_ES_EYE_SCAN_EN="TRUE",            # Must be TRUE for GTX
            )

        # TX clocking
        tx_reset_deglitched = Signal()
        tx_reset_deglitched.attr.add("no_retiming")
        self.sync += tx_reset_deglitched.eq(~tx_init.done)
        self.clock_domains.cd_rtio_tx = ClockDomain()
        if tx_mode == "single" or tx_mode == "master":
            self.specials += Instance("BUFG", i_I=self.txoutclk, o_O=self.cd_rtio_tx.clk)
        self.specials += AsyncResetSynchronizer(self.cd_rtio_tx, tx_reset_deglitched)

        # RX clocking
        rx_reset_deglitched = Signal()
        rx_reset_deglitched.attr.add("no_retiming")
        self.sync.rtio += rx_reset_deglitched.eq(~rx_init.done)
        self.clock_domains.cd_rtio_rx = ClockDomain()
        if rx_mode == "single" or rx_mode == "master":
            self.specials += Instance("BUFG", i_I=self.rxoutclk, o_O=self.cd_rtio_rx.clk),
        self.specials += AsyncResetSynchronizer(self.cd_rtio_rx, rx_reset_deglitched)

        self.comb += [
            txdata.eq(Cat(self.encoder.output[0], self.encoder.output[1])),
            self.decoders[0].input.eq(rxdata[:10]),
            self.decoders[1].input.eq(rxdata[10:])
        ]

        clock_aligner = BruteforceClockAligner(0b0101111100, rtio_clk_freq)
        self.submodules += clock_aligner
        self.comb += [
            clock_aligner.rxdata.eq(rxdata),
            rx_init.restart.eq(clock_aligner.restart),
            self.rx_ready.eq(clock_aligner.ready)
        ]



class GTX(Module, TransceiverInterface):
    def __init__(self, clock_pads, pads, sys_clk_freq, rtio_clk_freq=125e6, master=0):
        self.nchannels = nchannels = len(pads)
        self.gtxs = []
        self.rtio_clk_freq = rtio_clk_freq

        # # #

        refclk = Signal()
        stable_clkin_n = Signal()
        self.specials += Instance("IBUFDS_GTE2",
            i_CEB=stable_clkin_n,
            i_I=clock_pads.p,
            i_IB=clock_pads.n,
            o_O=refclk,
            p_CLKCM_CFG="0b1",
            p_CLKRCV_TRST="0b1",
            p_CLKSWING_CFG="0b11"
        )

        rtio_tx_clk = Signal()
        channel_interfaces = []
        for i in range(nchannels):
            if nchannels == 1:
                mode = "single"
            else:
                mode = "master" if i == master else "slave"
            # Note: RX phase alignment is to be done on individual lanes, not multi-lane.
            gtx = GTX_20X(refclk, pads[i], sys_clk_freq, rtio_clk_freq=rtio_clk_freq, tx_mode=mode, rx_mode="single")
            # Fan-out (to slave) / Fan-in (from master) of the TXUSRCLK
            if mode == "slave":
                self.comb += gtx.cd_rtio_tx.clk.eq(rtio_tx_clk)
            else:
                self.comb += rtio_tx_clk.eq(gtx.cd_rtio_tx.clk)
            self.gtxs.append(gtx)
            setattr(self.submodules, "gtx"+str(i), gtx)
            channel_interface = ChannelInterface(gtx.encoder, gtx.decoders)
            self.comb += channel_interface.rx_ready.eq(gtx.rx_ready)
            channel_interfaces.append(channel_interface)

        self.submodules.tx_phase_alignment = GTXInitPhaseAlignment([gtx.tx_init for gtx in self.gtxs])

        TransceiverInterface.__init__(self, channel_interfaces)
        for n, gtx in enumerate(self.gtxs):
            self.comb += [
                stable_clkin_n.eq(~self.stable_clkin.storage),
                gtx.txenable.eq(self.txenable.storage[n])
            ]

        # Connect master's `rtio_tx` clock to `rtio` clock
        self.comb += [
            self.cd_rtio.clk.eq(self.gtxs[master].cd_rtio_tx.clk),
            self.cd_rtio.rst.eq(reduce(or_, [gtx.cd_rtio_tx.rst for gtx in self.gtxs]))
        ]
        # Connect slave i's `rtio_rx` clock to `rtio_rxi` clock
        for i in range(nchannels):
            self.comb += [
                getattr(self, "cd_rtio_rx" + str(i)).clk.eq(self.gtxs[i].cd_rtio_rx.clk),
                getattr(self, "cd_rtio_rx" + str(i)).rst.eq(self.gtxs[i].cd_rtio_rx.rst)
            ]
