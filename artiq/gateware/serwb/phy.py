from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.misc import WaitTimer

from misoc.interconnect.csr import *

from artiq.gateware.serwb.kusphy import KUSSerdes
from artiq.gateware.serwb.s7phy import S7Serdes


# Master <--> Slave synchronization:
# 1) Master sends idle pattern (zeroes) to reset Slave.
# 2) Master sends K28.5 commas to allow Slave to calibrate, Slave sends idle pattern.
# 3) Slave sends K28.5 commas to allow Master to calibrate, Master sends K28.5 commas.
# 4) Master stops sending K28.5 commas.
# 5) Slave stops sending K28.5 commas.
# 6) Link is ready.

class _SerdesMasterInit(Module):
    def __init__(self, serdes, taps, timeout=1024):
        self.reset = Signal()
        self.ready = Signal()
        self.error = Signal()

        # # #

        self.delay = delay = Signal(max=taps)
        self.delay_min = delay_min = Signal(max=taps)
        self.delay_min_found = delay_min_found = Signal()
        self.delay_max = delay_max = Signal(max=taps)
        self.delay_max_found = delay_max_found = Signal()
        self.bitslip = bitslip = Signal(max=40)

        timer = WaitTimer(timeout)
        self.submodules += timer

        self.submodules.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.comb += self.fsm.reset.eq(self.reset)

        self.comb += serdes.rx_delay_inc.eq(1)

        fsm.act("IDLE",
            NextValue(delay, 0),
            NextValue(delay_min, 0),
            NextValue(delay_min_found, 0),
            NextValue(delay_max, 0),
            NextValue(delay_max_found, 0),
            serdes.rx_delay_rst.eq(1),
            NextValue(bitslip, 0),
            NextState("RESET_SLAVE"),
            serdes.tx_idle.eq(1)
        )
        fsm.act("RESET_SLAVE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("SEND_PATTERN")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("SEND_PATTERN",
            If(~serdes.rx_idle,
                NextState("WAIT_STABLE")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("WAIT_STABLE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CHECK_PATTERN")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("CHECK_PATTERN",
            If(~delay_min_found,
                If(serdes.rx_comma,
                    timer.wait.eq(1),
                    If(timer.done,
                        timer.wait.eq(0),
                        NextValue(delay_min, delay),
                        NextValue(delay_min_found, 1)
                    )
                ).Else(
                    NextState("INC_DELAY_BITSLIP")
                ),
            ).Else(
                If(~serdes.rx_comma,
                    NextValue(delay_max, delay),
                    NextValue(delay_max_found, 1),
                    NextState("CHECK_SAMPLING_WINDOW")
                ).Else(
                    NextState("INC_DELAY_BITSLIP")
                )
            ),
            serdes.tx_comma.eq(1)
        )
        self.comb += serdes.rx_bitslip_value.eq(bitslip)
        fsm.act("INC_DELAY_BITSLIP",
            NextState("WAIT_STABLE"),
            If(delay == (taps - 1),
                If(bitslip == (40 - 1),
                    NextState("ERROR")
                ).Else(
                    NextValue(delay_min_found, 0),
                    NextValue(bitslip, bitslip + 1)
                ),
                NextValue(delay, 0),
                serdes.rx_delay_rst.eq(1)
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_ce.eq(1)
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("CHECK_SAMPLING_WINDOW",
            If((delay_min == 0) |
               (delay_max == (taps - 1)) |
               ((delay_max - delay_min) < taps//16),
               NextValue(delay_min_found, 0),
               NextValue(delay_max_found, 0),
               NextState("WAIT_STABLE")
            ).Else(
                NextState("CONFIGURE_SAMPLING_WINDOW")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("CONFIGURE_SAMPLING_WINDOW",
            If(delay == (delay_min + (delay_max - delay_min)[1:]),
                NextState("READY")
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_inc.eq(1),
                serdes.rx_delay_ce.eq(1),
                NextState("WAIT_SAMPLING_WINDOW")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("WAIT_SAMPLING_WINDOW",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CONFIGURE_SAMPLING_WINDOW")
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("READY",
            self.ready.eq(1)
        )
        fsm.act("ERROR",
            self.error.eq(1)
        )


class _SerdesSlaveInit(Module, AutoCSR):
    def __init__(self, serdes, taps, timeout=1024):
        self.reset = Signal()
        self.ready = Signal()
        self.error = Signal()

        # # #

        self.delay = delay = Signal(max=taps)
        self.delay_min = delay_min = Signal(max=taps)
        self.delay_min_found = delay_min_found = Signal()
        self.delay_max = delay_max = Signal(max=taps)
        self.delay_max_found = delay_max_found = Signal()
        self.bitslip = bitslip = Signal(max=40)

        timer = WaitTimer(timeout)
        self.submodules += timer

        self.comb += self.reset.eq(serdes.rx_idle)

        self.comb += serdes.rx_delay_inc.eq(1)

        self.submodules.fsm = fsm = ResetInserter()(FSM(reset_state="IDLE"))
        fsm.act("IDLE",
            NextValue(delay, 0),
            NextValue(delay_min, 0),
            NextValue(delay_min_found, 0),
            NextValue(delay_max, 0),
            NextValue(delay_max_found, 0),
            serdes.rx_delay_rst.eq(1),
            NextValue(bitslip, 0),
            NextState("WAIT_STABLE"),
            serdes.tx_idle.eq(1)
        )
        fsm.act("WAIT_STABLE",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CHECK_PATTERN")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("CHECK_PATTERN",
            If(~delay_min_found,
                If(serdes.rx_comma,
                    timer.wait.eq(1),
                    If(timer.done,
                        timer.wait.eq(0),
                        NextValue(delay_min, delay),
                        NextValue(delay_min_found, 1)
                    )
                ).Else(
                    NextState("INC_DELAY_BITSLIP")
                ),
            ).Else(
                If(~serdes.rx_comma,
                    NextValue(delay_max, delay),
                    NextValue(delay_max_found, 1),
                    NextState("CHECK_SAMPLING_WINDOW")
                ).Else(
                    NextState("INC_DELAY_BITSLIP")
                )
            ),
            serdes.tx_idle.eq(1)
        )
        self.comb += serdes.rx_bitslip_value.eq(bitslip)
        fsm.act("INC_DELAY_BITSLIP",
            NextState("WAIT_STABLE"),
            If(delay == (taps - 1),
                If(bitslip == (40 - 1),
                    NextState("ERROR")
                ).Else(
                    NextValue(delay_min_found, 0),
                    NextValue(bitslip, bitslip + 1)
                ),
                NextValue(delay, 0),
                serdes.rx_delay_rst.eq(1)
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_ce.eq(1)
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("CHECK_SAMPLING_WINDOW",
            If((delay_min == 0) |
               (delay_max == (taps - 1)) |
               ((delay_max - delay_min) < taps//16),
               NextValue(delay_min_found, 0),
               NextValue(delay_max_found, 0),
               NextState("WAIT_STABLE")
            ).Else(
                NextState("CONFIGURE_SAMPLING_WINDOW")
            ),
            serdes.tx_idle.eq(1)
        )
        fsm.act("CONFIGURE_SAMPLING_WINDOW",
            If(delay == (delay_min + (delay_max - delay_min)[1:]),
                NextState("SEND_PATTERN")
            ).Else(
                NextValue(delay, delay + 1),
                serdes.rx_delay_inc.eq(1),
                serdes.rx_delay_ce.eq(1),
                NextState("WAIT_SAMPLING_WINDOW")
            )
        )
        fsm.act("WAIT_SAMPLING_WINDOW",
            timer.wait.eq(1),
            If(timer.done,
                timer.wait.eq(0),
                NextState("CONFIGURE_SAMPLING_WINDOW")
            )
        )
        fsm.act("SEND_PATTERN",
            timer.wait.eq(1),
            If(timer.done,
                If(~serdes.rx_comma,
                    NextState("READY")
                )
            ),
            serdes.tx_comma.eq(1)
        )
        fsm.act("READY",
            self.ready.eq(1)
        )
        fsm.act("ERROR",
            self.error.eq(1)
        )


class _SerdesControl(Module, AutoCSR):
    def __init__(self, init, mode="master"):
        if mode == "master":
            self.reset = CSR()
        self.ready = CSRStatus()
        self.error = CSRStatus()

        self.delay = CSRStatus(9)
        self.delay_min_found = CSRStatus()
        self.delay_min = CSRStatus(9)
        self.delay_max_found = CSRStatus()
        self.delay_max = CSRStatus(9)
        self.bitslip = CSRStatus(6)

        # # #

        if mode == "master":
            self.comb += init.reset.eq(self.reset.re)
        self.comb += [
            self.ready.status.eq(init.ready),
            self.error.status.eq(init.error),
            self.delay.status.eq(init.delay),
            self.delay_min_found.status.eq(init.delay_min_found),
            self.delay_min.status.eq(init.delay_min),
            self.delay_max_found.status.eq(init.delay_max_found),
            self.delay_max.status.eq(init.delay_max),
            self.bitslip.status.eq(init.bitslip)
        ]


class SERWBPLL(Module):
    def __init__(self, refclk_freq, linerate, vco_div=1):
        assert refclk_freq == 125e6
        assert linerate == 1.25e9

        self.lock = Signal()
        self.refclk = Signal()
        self.serwb_serdes_clk = Signal()
        self.serwb_serdes_20x_clk = Signal()
        self.serwb_serdes_5x_clk = Signal()

        # # #

        #----------------------------
        # refclk:              125MHz
        # vco:                1250MHz
        #----------------------------
        # serwb_serdes:      31.25MHz
        # serwb_serdes_20x:    625MHz
        # serwb_serdes_5x:  156.25MHz
        #----------------------------
        self.linerate = linerate

        pll_locked = Signal()
        pll_fb = Signal()
        pll_serwb_serdes_clk = Signal()
        pll_serwb_serdes_20x_clk = Signal()
        pll_serwb_serdes_5x_clk = Signal()
        self.specials += [
            Instance("PLLE2_BASE",
                p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

                # VCO @ 1.25GHz / vco_div
                p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=8.0,
                p_CLKFBOUT_MULT=10, p_DIVCLK_DIVIDE=vco_div,
                i_CLKIN1=self.refclk, i_CLKFBIN=pll_fb,
                o_CLKFBOUT=pll_fb,

                # 31.25MHz: serwb_serdes
                p_CLKOUT0_DIVIDE=40//vco_div, p_CLKOUT0_PHASE=0.0,
                o_CLKOUT0=pll_serwb_serdes_clk,

                # 625MHz: serwb_serdes_20x
                p_CLKOUT1_DIVIDE=2//vco_div, p_CLKOUT1_PHASE=0.0,
                o_CLKOUT1=pll_serwb_serdes_20x_clk,

                # 156.25MHz: serwb_serdes_5x
                p_CLKOUT2_DIVIDE=8//vco_div, p_CLKOUT2_PHASE=0.0,
                o_CLKOUT2=pll_serwb_serdes_5x_clk
            ),
            Instance("BUFG", 
                i_I=pll_serwb_serdes_clk, 
                o_O=self.serwb_serdes_clk),
            Instance("BUFG",
                i_I=pll_serwb_serdes_20x_clk,
                o_O=self.serwb_serdes_20x_clk),
            Instance("BUFG",
                i_I=pll_serwb_serdes_5x_clk,
                o_O=self.serwb_serdes_5x_clk)
        ]
        self.specials += MultiReg(pll_locked, self.lock)



class SERWBPHY(Module, AutoCSR):
    def __init__(self, device, pll, pads, mode="master"):
        assert mode in ["master", "slave"]
        if device[:4] == "xcku":
            taps = 512
            self.submodules.serdes = KUSSerdes(pll, pads, mode)
        elif device[:4] == "xc7a":
            taps = 32
            self.submodules.serdes = S7Serdes(pll, pads, mode)
        else:
            raise NotImplementedError
        if mode == "master":
            self.submodules.init = _SerdesMasterInit(self.serdes, taps)
        else:
            self.submodules.init = _SerdesSlaveInit(self.serdes, taps)
        self.submodules.control = _SerdesControl(self.init, mode)
