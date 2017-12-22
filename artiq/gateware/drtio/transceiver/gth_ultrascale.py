from litex.gen import *
from litex.gen.genlib.resetsync import AsyncResetSynchronizer
from litex.gen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *
from litex.soc.cores.code_8b10b import Encoder, Decoder

from drtio.common import TransceiverInterface, ChannelInterface
from drtio.gth_ultrascale_init import GTHInit
from drtio.clock_aligner import BruteforceClockAligner


class GTHChannelPLL(Module):
    def __init__(self, refclk, refclk_freq, linerate):
        self.refclk = refclk
        self.reset = Signal()
        self.lock = Signal()
        self.config = self.compute_config(refclk_freq, linerate)

    @staticmethod
    def compute_config(refclk_freq, linerate):
        for n1 in 4, 5:
            for n2 in 1, 2, 3, 4, 5:
                for m in 1, 2:
                    vco_freq = refclk_freq*(n1*n2)/m
                    if 2.0e9 <= vco_freq <= 6.25e9:
                        for d in 1, 2, 4, 8, 16:
                            current_linerate = vco_freq*2/d
                            if current_linerate == linerate:
                                return {"n1": n1, "n2": n2, "m": m, "d": d,
                                        "vco_freq": vco_freq,
                                        "clkin": refclk_freq,
                                        "linerate": linerate}
        msg = "No config found for {:3.2f} MHz refclk / {:3.2f} Gbps linerate."
        raise ValueError(msg.format(refclk_freq/1e6, linerate/1e9))

    def __repr__(self):
        r = """
GTHChannelPLL
==============
  overview:
  ---------
       +--------------------------------------------------+
       |                                                  |
       |   +-----+  +---------------------------+ +-----+ |
       |   |     |  | Phase Frequency Detector  | |     | |
CLKIN +----> /M  +-->       Charge Pump         +-> VCO +---> CLKOUT
       |   |     |  |       Loop Filter         | |     | |
       |   +-----+  +---------------------------+ +--+--+ |
       |              ^                              |    |
       |              |    +-------+    +-------+    |    |
       |              +----+  /N2  <----+  /N1  <----+    |
       |                   +-------+    +-------+         |
       +--------------------------------------------------+
                            +-------+
                   CLKOUT +->  2/D  +-> LINERATE
                            +-------+
  config:
  -------
    CLKIN    = {clkin}MHz
    CLKOUT   = CLKIN x (N1 x N2) / M = {clkin}MHz x ({n1} x {n2}) / {m}
             = {vco_freq}GHz
    LINERATE = CLKOUT x 2 / D = {vco_freq}GHz x 2 / {d}
             = {linerate}GHz
""".format(clkin=self.config["clkin"]/1e6,
           n1=self.config["n1"],
           n2=self.config["n2"],
           m=self.config["m"],
           vco_freq=self.config["vco_freq"]/1e9,
           d=self.config["d"],
           linerate=self.config["linerate"]/1e9)
        return r


class GTHQuadPLL(Module):
    def __init__(self, refclk, refclk_freq, linerate):
        self.clk = Signal()
        self.refclk = Signal()
        self.reset = Signal()
        self.lock = Signal()
        self.config = self.compute_config(refclk_freq, linerate)

        # # #

        self.specials += \
            Instance("GTHE3_COMMON",
                # common
                i_GTREFCLK00=refclk,
                i_GTREFCLK01=refclk,
                i_QPLLRSVD1=0,
                i_QPLLRSVD2=0,
                i_QPLLRSVD3=0,
                i_QPLLRSVD4=0,
                i_BGBYPASSB=1,
                i_BGMONITORENB=1,
                i_BGPDB=1,
                i_BGRCALOVRD=0b11111,
                i_BGRCALOVRDENB=0b1,
                i_RCALENB=1,

                # qpll0
                p_QPLL0_FBDIV=self.config["n"],
                p_QPLL0_REFCLK_DIV=self.config["m"],
                i_QPLL0CLKRSVD0=0,
                i_QPLL0CLKRSVD1=0,
                i_QPLL0LOCKDETCLK=ClockSignal(),
                i_QPLL0LOCKEN=1,
                o_QPLL0LOCK=self.lock if self.config["qpll"] == "qpll0" else
                            Signal(),
                o_QPLL0OUTCLK=self.clk if self.config["qpll"] == "qpll0" else
                              Signal(),
                o_QPLL0OUTREFCLK=self.refclk if self.config["qpll"] == "qpll0" else
                                 Signal(),
                i_QPLL0PD=0 if self.config["qpll"] == "qpll0" else 1,
                i_QPLL0REFCLKSEL=0b001,
                i_QPLL0RESET=self.reset,

                # qpll1
                p_QPLL1_FBDIV=self.config["n"],
                p_QPLL1_REFCLK_DIV=self.config["m"],
                i_QPLL1CLKRSVD0=0,
                i_QPLL1CLKRSVD1=0,
                i_QPLL1LOCKDETCLK=ClockSignal(),
                i_QPLL1LOCKEN=1,
                o_QPLL1LOCK=self.lock if self.config["qpll"] == "qpll1" else
                            Signal(),
                o_QPLL1OUTCLK=self.clk if self.config["qpll"] == "qpll1" else
                              Signal(),
                o_QPLL1OUTREFCLK=self.refclk if self.config["qpll"] == "qpll1" else
                                 Signal(),
                i_QPLL1PD=0 if self.config["qpll"] == "qpll1" else 1,
                i_QPLL1REFCLKSEL=0b001,
                i_QPLL1RESET=self.reset,
             )

    @staticmethod
    def compute_config(refclk_freq, linerate):
        for n in [16, 20, 32, 40, 60, 64, 66, 75, 80, 84,
                  90, 96, 100, 112, 120, 125, 150, 160]:
            for m in 1, 2, 3, 4:
                vco_freq = refclk_freq*n/m
                if 8e9 <= vco_freq <= 13e9:
                    qpll = "qpll1"
                elif 9.8e9 <= vco_freq <= 16.375e9:
                    qpll = "qpll0"
                else:
                    qpll = None
                if qpll is not None:
                    for d in 1, 2, 4, 8, 16:
                        current_linerate = (vco_freq/2)*2/d
                        if current_linerate == linerate:
                            return {"n": n, "m": m, "d": d,
                                    "vco_freq": vco_freq,
                                    "qpll": qpll,
                                    "clkin": refclk_freq,
                                    "clkout": vco_freq/2,
                                    "linerate": linerate}
        msg = "No config found for {:3.2f} MHz refclk / {:3.2f} Gbps linerate."
        raise ValueError(msg.format(refclk_freq/1e6, linerate/1e9))

    def __repr__(self):
        r = """
GTXQuadPLL
===========
  overview:
  ---------
       +-------------------------------------------------------------++
       |                                          +------------+      |
       |   +-----+  +---------------------------+ |   QPLL0    | +--+ |
       |   |     |  | Phase Frequency Detector  +->    VCO     | |  | |
CLKIN +----> /M  +-->       Charge Pump         | +------------+->/2+--> CLKOUT
       |   |     |  |       Loop Filter         +->   QPLL1    | |  | |
       |   +-----+  +---------------------------+ |    VCO     | +--+ |
       |              ^                           +-----+------+      |
       |              |        +-------+                |             |
       |              +--------+  /N   <----------------+             |
       |                       +-------+                              |
       +--------------------------------------------------------------+
                               +-------+
                      CLKOUT +->  2/D  +-> LINERATE
                               +-------+
  config:
  -------
    CLKIN    = {clkin}MHz
    CLKOUT   = CLKIN x N / (2 x M) = {clkin}MHz x {n} / (2 x {m})
             = {clkout}GHz
    VCO      = {vco_freq}GHz ({qpll})
    LINERATE = CLKOUT x 2 / D = {clkout}GHz x 2 / {d}
             = {linerate}GHz
""".format(clkin=self.config["clkin"]/1e6,
           n=self.config["n"],
           m=self.config["m"],
           clkout=self.config["clkout"]/1e9,
           vco_freq=self.config["vco_freq"]/1e9,
           qpll=self.config["qpll"].upper(),
           d=self.config["d"],
           linerate=self.config["linerate"]/1e9)
        return r


class GTHSingle(Module):
    def __init__(self, pll, tx_pads, rx_pads, sys_clk_freq, dw=20, mode="master"):
        assert (dw == 20) or (dw == 40)
        assert mode in ["master", "slave"]

        # # #

        nwords = dw//10

        use_cpll = isinstance(pll, GTHChannelPLL)
        use_qpll0 = isinstance(pll, GTHQuadPLL) and pll.config["qpll"] == "qpll0"
        use_qpll1 = isinstance(pll, GTHQuadPLL) and pll.config["qpll"] == "qpll1"

        self.submodules.encoder = encoder = ClockDomainsRenamer("rtio_tx")(
            Encoder(nwords, True))
        self.submodules.decoders = decoders = [ClockDomainsRenamer("rtio_rx")(
            (Decoder(True))) for _ in range(nwords)]
        self.rx_ready = Signal()

        self.rtio_clk_freq = pll.config["linerate"]/dw

        # transceiver direct clock outputs
        # useful to specify clock constraints in a way palatable to Vivado
        self.txoutclk = Signal()
        self.rxoutclk = Signal()

        # # #

        # TX generates RTIO clock, init must be in system domain
        tx_init = GTHInit(sys_clk_freq, False)
        # RX receives restart commands from RTIO domain
        rx_init = ClockDomainsRenamer("rtio_tx")(
            GTHInit(self.rtio_clk_freq, True))
        self.submodules += tx_init, rx_init
        self.comb += [
            tx_init.plllock.eq(pll.lock),
            rx_init.plllock.eq(pll.lock)
        ]

        txdata = Signal(dw)
        rxdata = Signal(dw)
        rxphaligndone = Signal()
        self.specials += \
            Instance("GTHE3_CHANNEL",
                # Reset modes
                i_GTRESETSEL=0,
                i_RESETOVRD=0,

                # PMA Attributes
                p_PMA_RSV1=0xf800,
                p_RX_BIAS_CFG0=0x0AB4,
                p_RX_CM_TRIM=0b1010,
                p_RX_CLK25_DIV=5,
                p_TX_CLK25_DIV=5,

                # Power-Down Attributes
                p_PD_TRANS_TIME_FROM_P2=0x3c,
                p_PD_TRANS_TIME_NONE_P2=0x19,
                p_PD_TRANS_TIME_TO_P2=0x64,

                # CPLL
                p_CPLL_CFG0=0x67f8,
                p_CPLL_CFG1=0xa4ac,
                p_CPLL_CFG2=0xf007,
                p_CPLL_CFG3=0x0000,
                p_CPLL_FBDIV=1 if use_qpll0 or use_qpll1 else pll.config["n2"],
                p_CPLL_FBDIV_45=4 if use_qpll0 or use_qpll1 else pll.config["n1"],
                p_CPLL_REFCLK_DIV=1 if use_qpll0 or use_qpll1 else pll.config["m"],
                p_RXOUT_DIV=pll.config["d"],
                p_TXOUT_DIV=pll.config["d"],
                i_CPLLRESET=0,
                i_CPLLPD=0 if use_qpll0 or use_qpll1 else pll.reset,
                o_CPLLLOCK=Signal() if use_qpll0 or use_qpll1 else pll.lock,
                i_CPLLLOCKEN=1,
                i_CPLLREFCLKSEL=0b001,
                i_TSTIN=2**20-1,
                i_GTREFCLK0=0 if use_qpll0 or use_qpll1 else pll.refclk,

                # QPLL
                i_QPLL0CLK=0 if use_cpll or use_qpll1 else pll.clk,
                i_QPLL0REFCLK=0 if use_cpll or use_qpll1 else pll.refclk,
                i_QPLL1CLK=0 if use_cpll or use_qpll0 else pll.clk,
                i_QPLL1REFCLK=0 if use_cpll or use_qpll0 else pll.refclk,

                # TX clock
                p_TXBUF_EN="FALSE",
                p_TX_XCLK_SEL="TXUSR",
                o_TXOUTCLK=self.txoutclk,
                i_TXSYSCLKSEL=0b00 if use_cpll else 0b10 if use_qpll0 else 0b11,
                i_TXPLLCLKSEL=0b00 if use_cpll else 0b11 if use_qpll0 else 0b10,
                i_TXOUTCLKSEL=0b11,

                # TX Startup/Reset
                i_GTTXRESET=tx_init.gtXxreset,
                o_TXRESETDONE=tx_init.Xxresetdone,
                i_TXDLYSRESET=tx_init.Xxdlysreset,
                o_TXDLYSRESETDONE=tx_init.Xxdlysresetdone,
                o_TXPHALIGNDONE=tx_init.Xxphaligndone,
                i_TXUSERRDY=tx_init.Xxuserrdy,
                i_TXSYNCMODE=1,

                # TX data
                p_TX_DATA_WIDTH=dw,
                p_TX_INT_DATAWIDTH=dw == 40,
                i_TXCTRL0=Cat(*[txdata[10*i+8] for i in range(nwords)]),
                i_TXCTRL1=Cat(*[txdata[10*i+9] for i in range(nwords)]),
                i_TXDATA=Cat(*[txdata[10*i:10*i+8] for i in range(nwords)]),
                i_TXUSRCLK=ClockSignal("rtio_tx"),
                i_TXUSRCLK2=ClockSignal("rtio_tx"),

                # TX electrical
                i_TXPD=0b00,
                p_TX_CLKMUX_EN=1,
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
                p_RXBUF_EN="FALSE",
                p_RX_XCLK_SEL="RXUSR",
                i_RXSYSCLKSEL=0b00,
                i_RXOUTCLKSEL=0b010,
                i_RXPLLCLKSEL=0b00,
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
                p_RX_DATA_WIDTH=dw,
                p_RX_INT_DATAWIDTH=dw == 40,
                o_RXCTRL0=Cat(*[rxdata[10*i+8] for i in range(nwords)]),
                o_RXCTRL1=Cat(*[rxdata[10*i+9] for i in range(nwords)]),
                o_RXDATA=Cat(*[rxdata[10*i:10*i+8] for i in range(nwords)]),

                # RX electrical
                i_RXPD=0b00,
                p_RX_CLKMUX_EN=1,
                i_RXELECIDLEMODE=0b11,

                # Pads
                i_GTHRXP=rx_pads.p,
                i_GTHRXN=rx_pads.n,
                o_GTHTXP=tx_pads.p,
                o_GTHTXN=tx_pads.n
            )

        # tx clocking
        tx_reset_deglitched = Signal()
        tx_reset_deglitched.attr.add("no_retiming")
        self.sync += tx_reset_deglitched.eq(~tx_init.done)
        self.clock_domains.cd_rtio_tx = ClockDomain()
        if mode == "master":
            tx_bufg_div = pll.config["clkin"]/self.rtio_clk_freq
            assert tx_bufg_div == int(tx_bufg_div)
            self.specials += \
                Instance("BUFG_GT", i_I=self.txoutclk, o_O=self.cd_rtio_tx.clk,
                    i_DIV=int(tx_bufg_div)-1)
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
        clock_aligner = BruteforceClockAligner(0b0101111100, self.rtio_clk_freq)
        self.submodules += clock_aligner
        self.comb += [
            clock_aligner.rxdata.eq(rxdata),
            rx_init.restart.eq(clock_aligner.restart),
            self.rx_ready.eq(clock_aligner.ready)
        ]


class GTH(Module, TransceiverInterface):
    def __init__(self, plls, tx_pads, rx_pads, sys_clk_freq, dw, master=0):
        self.nchannels = nchannels = len(tx_pads)
        self.gths = []

        # # #

        nwords = dw//10

        rtio_tx_clk = Signal()
        channel_interfaces = []
        for i in range(nchannels):
            mode = "master" if i == master else "slave"
            gth = GTHSingle(plls[i], tx_pads[i], rx_pads[i], sys_clk_freq, dw, mode)
            if mode == "master":
                self.comb += rtio_tx_clk.eq(gth.cd_rtio_tx.clk)
            else:
                self.comb += gth.cd_rtio_tx.clk.eq(rtio_tx_clk)
            self.gths.append(gth)
            setattr(self.submodules, "gth"+str(i), gth)
            channel_interface = ChannelInterface(gth.encoder, gth.decoders)
            self.comb += channel_interface.rx_ready.eq(gth.rx_ready)
            channel_interfaces.append(channel_interface)

        TransceiverInterface.__init__(self, channel_interfaces)

        # rtio clock domain (clock from gth tx0, ored reset from all gth txs)
        self.comb += self.cd_rtio.clk.eq(ClockSignal("gth0_rtio_tx"))
        rtio_rst = Signal()
        for i in range(nchannels):
            rtio_rst.eq(rtio_rst | ResetSignal("gth" + str(i) + "rtio_tx"))
            new_rtio_rst = Signal()
            rtio_rst = new_rtio_rst
        self.comb += self.cd_rtio.rst.eq(rtio_rst)

        # rtio_rx clock domains
        for i in range(nchannels):
            self.comb += [
                getattr(self, "cd_rtio_rx" + str(i)).clk.eq(self.gths[i].cd_rtio_rx.clk),
                getattr(self, "cd_rtio_rx" + str(i)).rst.eq(self.gths[i].cd_rtio_rx.rst)
            ]
