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
    def __init__(self, refclk, pads, sys_clk_freq, rtio_clk_freq, dw, mode):
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
        # useful to specify clock constraints in a way palatable to Vivado
        self.txoutclk = Signal()
        self.rxoutclk = Signal()

        # # #

        # TX generates RTIO clock, init must be in system domain
        self.submodules.tx_init = tx_init = GTHInit(sys_clk_freq, False)
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
                p_CPLL_FBDIV=5,
                p_CPLL_FBDIV_45=4,
                p_CPLL_REFCLK_DIV=1,
                p_RXOUT_DIV=2,
                p_TXOUT_DIV=2,
                i_CPLLRESET=0,
                i_CPLLPD=cpll_reset,
                o_CPLLLOCK=cpll_lock,
                i_CPLLLOCKEN=1,
                i_CPLLREFCLKSEL=0b001,
                i_TSTIN=2**20-1,
                i_GTREFCLK0=refclk,

                # TX clock
                p_TXBUF_EN="FALSE",
                p_TX_XCLK_SEL="TXUSR",
                o_TXOUTCLK=self.txoutclk,
                i_TXSYSCLKSEL=0b00,
                i_TXPLLCLKSEL=0b00,
                i_TXOUTCLKSEL=0b11,

                # TX Startup/Reset
                i_GTTXRESET=tx_init.gtXxreset,
                o_TXRESETDONE=tx_init.Xxresetdone,
                i_TXDLYSRESET=tx_init.Xxdlysreset if mode != "slave" else self.txdlysreset,
                o_TXDLYSRESETDONE=tx_init.Xxdlysresetdone,
                o_TXPHALIGNDONE=tx_init.Xxphaligndone,
                i_TXUSERRDY=tx_init.Xxuserrdy,
                i_TXSYNCMODE=mode != "slave",
                p_TXSYNC_MULTILANE=0 if mode == "single" else 1,
                p_TXSYNC_OVRD=0,
                i_TXSYNCALLIN=self.txsyncallin,
                i_TXSYNCIN=self.txsyncin,
                o_TXSYNCOUT=self.txsyncout,

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
                i_GTHRXP=pads.rxp,
                i_GTHRXN=pads.rxn,
                o_GTHTXP=pads.txp,
                o_GTHTXN=pads.txn
            )
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
        if mode == "master" or mode == "single":
            self.specials += \
                Instance("BUFG_GT", i_I=self.txoutclk, o_O=self.cd_rtio_tx.clk, i_DIV=0)
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
    def __init__(self, clock_pads, data_pads, sys_clk_freq, rtio_clk_freq, dw=20, master=0):
        self.nchannels = nchannels = len(data_pads)
        self.gths = []

        # # #

        refclk = Signal()
        self.specials += Instance("IBUFDS_GTE3",
            i_CEB=0,
            i_I=clock_pads.p,
            i_IB=clock_pads.n,
            o_O=refclk)

        rtio_tx_clk = Signal()
        channel_interfaces = []
        for i in range(nchannels):
            if nchannels == 1:
                mode = "single"
            else:
                mode = "master" if i == master else "slave"
            gth = GTHSingle(refclk, data_pads[i], sys_clk_freq, rtio_clk_freq, dw, mode)
            if mode == "slave":
                self.comb += gth.cd_rtio_tx.clk.eq(rtio_tx_clk)
            else:
                self.comb += rtio_tx_clk.eq(gth.cd_rtio_tx.clk)
            self.gths.append(gth)
            setattr(self.submodules, "gth"+str(i), gth)
            channel_interface = ChannelInterface(gth.encoder, gth.decoders)
            self.comb += channel_interface.rx_ready.eq(gth.rx_ready)
            channel_interfaces.append(channel_interface)

        self.submodules.tx_phase_alignment = GTHTXPhaseAlignement(self.gths)

        TransceiverInterface.__init__(self, channel_interfaces)
        # GTH PLLs recover on their own from an interrupted clock input.
        # stable_clkin can be ignored.

        self.comb += [
            self.cd_rtio.clk.eq(self.gths[master].cd_rtio_tx.clk),
            self.cd_rtio.rst.eq(reduce(or_, [gth.cd_rtio_tx.rst for gth in self.gths]))
        ]
        for i in range(nchannels):
            self.comb += [
                getattr(self, "cd_rtio_rx" + str(i)).clk.eq(self.gths[i].cd_rtio_rx.clk),
                getattr(self, "cd_rtio_rx" + str(i)).rst.eq(self.gths[i].cd_rtio_rx.rst)
            ]
