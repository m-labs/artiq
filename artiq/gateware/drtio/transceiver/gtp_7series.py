from functools import reduce
from operator import or_

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from misoc.cores.code_8b10b import Encoder, Decoder

from artiq.gateware.drtio.core import TransceiverInterface, ChannelInterface
from artiq.gateware.drtio.transceiver.clock_aligner import BruteforceClockAligner
from artiq.gateware.drtio.transceiver.gtp_7series_init import *


class GTPSingle(Module):
    def __init__(self, qpll_channel, pads, sys_clk_freq, rtio_clk_freq, mode):
        if mode != "master":
            raise NotImplementedError
        self.submodules.encoder = encoder = ClockDomainsRenamer("rtio_tx")(
            Encoder(2, True))
        self.submodules.decoders = decoders = [ClockDomainsRenamer("rtio_rx")(
            (Decoder(True))) for _ in range(2)]
        self.rx_ready = Signal()

        # transceiver direct clock outputs
        # useful to specify clock constraints in a way palatable to Vivado
        self.txoutclk = Signal()
        self.rxoutclk = Signal()

        # # #

        # TX generates RTIO clock, init must be in system domain
        tx_init = GTPTXInit(sys_clk_freq)
        # RX receives restart commands from RTIO domain
        rx_init = ClockDomainsRenamer("rtio_tx")(GTPRXInit(rtio_clk_freq))
        self.submodules += tx_init, rx_init

        self.comb += [
            qpll_channel.reset.eq(tx_init.pllreset),
            tx_init.plllock.eq(qpll_channel.lock),
            rx_init.plllock.eq(qpll_channel.lock),
        ]

        txdata = Signal(20)
        rxdata = Signal(20)
        rxphaligndone = Signal()
        self.specials += \
            Instance("GTPE2_CHANNEL",
                # Reset modes
                i_GTRESETSEL=0,
                i_RESETOVRD=0,

                # DRP
                i_DRPADDR=rx_init.drpaddr,
                i_DRPCLK=ClockSignal("rtio_tx"),
                i_DRPDI=rx_init.drpdi,
                o_DRPDO=rx_init.drpdo,
                i_DRPEN=rx_init.drpen,
                o_DRPRDY=rx_init.drprdy,
                i_DRPWE=rx_init.drpwe,

                # PMA Attributes
                p_PMA_RSV=0x333,
                p_PMA_RSV2=0x2040,
                p_PMA_RSV3=0,
                p_PMA_RSV4=0,
                p_RX_BIAS_CFG=0b0000111100110011,
                p_RX_CM_SEL=0b01,
                p_RX_CM_TRIM=0b1010,
                p_RX_OS_CFG=0b10000000,
                p_RXLPM_IPCM_CFG=1,
                i_RXELECIDLEMODE=0b11,
                i_RXOSINTCFG=0b0010,
                i_RXOSINTEN=1,

                # Power-Down Attributes
                p_PD_TRANS_TIME_FROM_P2=0x3c,
                p_PD_TRANS_TIME_NONE_P2=0x3c,
                p_PD_TRANS_TIME_TO_P2=0x64,

                # QPLL
                i_PLL0CLK=qpll_channel.clk,
                i_PLL0REFCLK=qpll_channel.refclk,

                # TX clock
                p_TXBUF_EN="FALSE",
                p_TX_XCLK_SEL="TXUSR",
                o_TXOUTCLK=self.txoutclk,
                p_TXOUT_DIV=2,
                i_TXSYSCLKSEL=0b00,
                i_TXOUTCLKSEL=0b11,

                # TX Startup/Reset
                i_GTTXRESET=tx_init.gttxreset,
                o_TXRESETDONE=tx_init.txresetdone,
                p_TXSYNC_OVRD=1,
                i_TXDLYSRESET=tx_init.txdlysreset,
                o_TXDLYSRESETDONE=tx_init.txdlysresetdone,
                i_TXPHINIT=tx_init.txphinit,
                o_TXPHINITDONE=tx_init.txphinitdone,
                i_TXPHALIGNEN=1,
                i_TXPHALIGN=tx_init.txphalign,
                o_TXPHALIGNDONE=tx_init.txphaligndone,
                i_TXDLYEN=tx_init.txdlyen,
                i_TXUSERRDY=tx_init.txuserrdy,

                # TX data
                p_TX_DATA_WIDTH=20,
                i_TXCHARDISPMODE=Cat(txdata[9], txdata[19]),
                i_TXCHARDISPVAL=Cat(txdata[8], txdata[18]),
                i_TXDATA=Cat(txdata[:8], txdata[10:18]),
                i_TXUSRCLK=ClockSignal("rtio_tx"),
                i_TXUSRCLK2=ClockSignal("rtio_tx"),

                # TX electrical
                i_TXBUFDIFFCTRL=0b100,
                i_TXDIFFCTRL=0b1000,

                # RX Startup/Reset
                i_GTRXRESET=rx_init.gtrxreset,
                o_RXRESETDONE=rx_init.rxresetdone,
                i_RXDLYSRESET=rx_init.rxdlysreset,
                o_RXDLYSRESETDONE=rx_init.rxdlysresetdone,
                o_RXPHALIGNDONE=rxphaligndone,
                i_RXSYNCALLIN=rxphaligndone,
                i_RXUSERRDY=rx_init.rxuserrdy,
                i_RXSYNCIN=0,
                i_RXSYNCMODE=1,
                p_RXSYNC_MULTILANE=0,
                p_RXSYNC_OVRD=0,
                o_RXSYNCDONE=rx_init.rxsyncdone,
                p_RXPMARESET_TIME=0b11,
                o_RXPMARESETDONE=rx_init.rxpmaresetdone,

                # RX clock
                p_RX_CLK25_DIV=5,
                p_TX_CLK25_DIV=5,
                p_RX_XCLK_SEL="RXUSR",
                p_RXOUT_DIV=2,
                i_RXSYSCLKSEL=0b00,
                i_RXOUTCLKSEL=0b010,
                o_RXOUTCLK=self.rxoutclk,
                i_RXUSRCLK=ClockSignal("rtio_rx"),
                i_RXUSRCLK2=ClockSignal("rtio_rx"),
                p_RXCDR_CFG=0x0000107FE206001041010,
                p_RXPI_CFG1=1,
                p_RXPI_CFG2=1,

                # RX Clock Correction Attributes
                p_CLK_CORRECT_USE="FALSE",

                # RX data
                p_RXBUF_EN="FALSE",
                p_RXDLY_CFG=0x001f,
                p_RXDLY_LCFG=0x030,
                p_RXPHDLY_CFG=0x084020,
                p_RXPH_CFG=0xc00002,
                p_RX_DATA_WIDTH=20,
                i_RXCOMMADETEN=1,
                i_RXDLYBYPASS=0,
                i_RXDDIEN=1,
                o_RXDISPERR=Cat(rxdata[9], rxdata[19]),
                o_RXCHARISK=Cat(rxdata[8], rxdata[18]),
                o_RXDATA=Cat(rxdata[:8], rxdata[10:18]),

                # Pads
                i_GTPRXP=pads.rxp,
                i_GTPRXN=pads.rxn,
                o_GTPTXP=pads.txp,
                o_GTPTXN=pads.txn
            )

        # tx clocking
        tx_reset_deglitched = Signal()
        tx_reset_deglitched.attr.add("no_retiming")
        self.sync += tx_reset_deglitched.eq(~tx_init.done)
        self.clock_domains.cd_rtio_tx = ClockDomain()
        if mode == "master":
            txoutclk_bufg = Signal()
            txoutclk_bufr = Signal()
            tx_bufr_div = 150.e6/rtio_clk_freq
            assert tx_bufr_div == int(tx_bufr_div)
            self.specials += [
                Instance("BUFG", i_I=self.txoutclk, o_O=txoutclk_bufg),
                Instance("BUFR", i_I=txoutclk_bufg, o_O=txoutclk_bufr,
                    i_CE=1, p_BUFR_DIVIDE=str(int(tx_bufr_div))),
                Instance("BUFG", i_I=txoutclk_bufr, o_O=self.cd_rtio_tx.clk)
            ]
        self.specials += AsyncResetSynchronizer(self.cd_rtio_tx, tx_reset_deglitched)

        # rx clocking
        rx_reset_deglitched = Signal()
        rx_reset_deglitched.attr.add("no_retiming")
        self.sync.rtio_tx += rx_reset_deglitched.eq(~rx_init.done)
        self.clock_domains.cd_rtio_rx = ClockDomain()
        self.specials += [
            Instance("BUFG", i_I=self.rxoutclk, o_O=self.cd_rtio_rx.clk),
            AsyncResetSynchronizer(self.cd_rtio_rx, rx_reset_deglitched)
        ]

        # tx data
        self.comb += txdata.eq(Cat(*[encoder.output[i] for i in range(2)]))

        # rx data
        for i in range(2):
            self.comb += decoders[i].input.eq(rxdata[10*i:10*(i+1)])

        # clock alignment
        clock_aligner = BruteforceClockAligner(0b0101111100, rtio_clk_freq, check_period=10e-3)
        self.submodules += clock_aligner
        self.comb += [
            clock_aligner.rxdata.eq(rxdata),
            rx_init.restart.eq(clock_aligner.restart),
            self.rx_ready.eq(clock_aligner.ready)
        ]


class GTP(Module, TransceiverInterface):
    def __init__(self, qpll_channel, data_pads, sys_clk_freq, rtio_clk_freq, master=0):
        self.nchannels = nchannels = len(data_pads)
        self.gtps = []
        if nchannels > 1:
            raise NotImplementedError

        # # #

        rtio_tx_clk = Signal()
        channel_interfaces = []
        for i in range(nchannels):
            mode = "master" if i == master else "slave"
            gtp = GTPSingle(qpll_channel, data_pads[i], sys_clk_freq, rtio_clk_freq, mode)
            if mode == "master":
                self.comb += rtio_tx_clk.eq(gtp.cd_rtio_tx.clk)
            else:
                self.comb += gtp.cd_rtio_tx.clk.eq(rtio_tx_clk)
            self.gtps.append(gtp)
            setattr(self.submodules, "gtp"+str(i), gtp)
            channel_interface = ChannelInterface(gtp.encoder, gtp.decoders)
            self.comb += channel_interface.rx_ready.eq(gtp.rx_ready)
            channel_interfaces.append(channel_interface)

        TransceiverInterface.__init__(self, channel_interfaces)

        self.comb += [
            self.cd_rtio.clk.eq(self.gtps[master].cd_rtio_tx.clk),
            self.cd_rtio.rst.eq(reduce(or_, [gtp.cd_rtio_tx.rst for gtp in self.gtps]))
        ]
        for i in range(nchannels):
            self.comb += [
                getattr(self, "cd_rtio_rx" + str(i)).clk.eq(self.gtps[i].cd_rtio_rx.clk),
                getattr(self, "cd_rtio_rx" + str(i)).rst.eq(self.gtps[i].cd_rtio_rx.rst)
            ]
