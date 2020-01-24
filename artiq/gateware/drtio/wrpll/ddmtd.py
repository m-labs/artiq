from migen import *
from migen.genlib.cdc import PulseSynchronizer, MultiReg
from migen.genlib.fsm import FSM
from misoc.interconnect.csr import *


class DDMTDSamplerExtFF(Module):
    def __init__(self, ddmtd_inputs):
        self.rec_clk = Signal()
        self.main_xo = Signal()

        # # #

        # TODO: s/h timing at FPGA pads
        if hasattr(ddmtd_inputs, "rec_clk"):
            rec_clk_1 = ddmtd_inputs.rec_clk
        else:
            rec_clk_1 = Signal()
            self.specials += Instance("IBUFDS",
                i_I=ddmtd_inputs.rec_clk_p, i_IB=ddmtd_inputs.rec_clk_n,
                o_O=rec_clk_1)
        if hasattr(ddmtd_inputs, "main_xo"):
            main_xo_1 = ddmtd_inputs.main_xo
        else:
            main_xo_1 = Signal()
            self.specials += Instance("IBUFDS",
                i_I=ddmtd_inputs.main_xo_p, i_IB=ddmtd_inputs.main_xo_n,
                o_O=main_xo_1)
        self.specials += [
            Instance("FD", i_C=ClockSignal("helper"),
                i_D=rec_clk_1, o_Q=self.rec_clk,
                attr={("IOB", "TRUE")}),
            Instance("FD", i_C=ClockSignal("helper"),
                i_D=main_xo_1, o_Q=self.main_xo,
                attr={("IOB", "TRUE")}),
        ]


class DDMTDSamplerGTP(Module):
    def __init__(self, gtp, main_xo_pads):
        self.rec_clk = Signal()
        self.main_xo = Signal()

        # # #

        # Getting the main XO signal from IBUFDS_GTE2 is problematic because
        # the transceiver PLL craps out if an improper clock signal is applied,
        # so we are disabling the buffer until the clock is stable.
        main_xo_se = Signal()
        rec_clk_1 = Signal()
        main_xo_1 = Signal()
        self.specials += [
            Instance("IBUFDS",
                i_I=main_xo_pads.p, i_IB=main_xo_pads.n,
                o_O=main_xo_se),
            Instance("FD", i_C=ClockSignal("helper"),
                i_D=gtp.cd_rtio_rx0.clk, o_Q=rec_clk_1,
                attr={("DONT_TOUCH", "TRUE")}),
            Instance("FD", i_C=ClockSignal("helper"),
                i_D=rec_clk_1, o_Q=self.rec_clk,
                attr={("DONT_TOUCH", "TRUE")}),
            Instance("FD", i_C=ClockSignal("helper"),
                i_D=main_xo_se, o_Q=main_xo_1,
                attr={("IOB", "TRUE")}),
            Instance("FD", i_C=ClockSignal("helper"),
                i_D=main_xo_1, o_Q=self.main_xo,
                attr={("DONT_TOUCH", "TRUE")}),
        ]


class DDMTDDeglitcherFirstEdge(Module):
    def __init__(self, input_signal, blind_period=128):
        self.detect = Signal()
        self.tag_correction = 0

        rising = Signal()
        input_signal_r = Signal()
        self.sync.helper += [
            input_signal_r.eq(input_signal),
            rising.eq(input_signal & ~input_signal_r)
        ]

        blind_counter = Signal(max=blind_period)
        self.sync.helper += [
            If(blind_counter != 0, blind_counter.eq(blind_counter - 1)),
            If(rising, blind_counter.eq(blind_period - 1)),
            self.detect.eq(rising & (blind_counter == 0))
        ]


class DDMTD(Module, AutoCSR):
    def __init__(self, counter, input_signal):
        self.arm = CSR()
        self.tag = CSRStatus(len(counter))

        # in helper clock domain
        self.h_tag = Signal(len(counter))
        self.h_tag_update = Signal()

        # # #

        deglitcher = DDMTDDeglitcherFirstEdge(input_signal)
        self.submodules += deglitcher

        self.sync.helper += [
            self.h_tag_update.eq(0),
            If(deglitcher.detect,
                self.h_tag_update.eq(1),
                self.h_tag.eq(counter + deglitcher.tag_correction)
            )
        ]

        tag_update_ps = PulseSynchronizer("helper", "sys")
        self.submodules += tag_update_ps
        self.comb += tag_update_ps.i.eq(self.h_tag_update)
        tag_update = Signal()
        self.sync += tag_update.eq(tag_update_ps.o)

        tag = Signal(len(counter))
        self.h_tag.attr.add("no_retiming")
        self.specials += MultiReg(self.h_tag, tag)

        self.sync += [
            If(self.arm.re & self.arm.r, self.arm.w.eq(1)),
            If(tag_update,
                If(self.arm.w, self.tag.status.eq(tag)),
                self.arm.w.eq(0),
            )
        ]


class Collector(Module):
    def __init__(self, N):
        self.tag_helper = Signal((N, True))
        self.tag_helper_update = Signal()
        self.tag_main = Signal((N, True))
        self.tag_main_update = Signal()

        self.output = Signal((N + 1, True))

        # # #

        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        tag_collector = Signal((N + 1, True))
        fsm.act("IDLE",
            If(self.tag_main_update & self.tag_helper_update,
                NextValue(tag_collector, 0),
                NextState("UPDATE")
            ).Elif(self.tag_main_update,
                NextValue(tag_collector, self.tag_main),
                NextState("WAITHELPER")
            ).Elif(self.tag_helper_update,
                NextValue(tag_collector, -self.tag_helper),
                NextState("WAITMAIN")
            )
        )
        fsm.act("WAITHELPER",
            If(self.tag_helper_update,
                NextValue(tag_collector, tag_collector - self.tag_helper),
                NextState("LEADCHECK")
            )
        )
        fsm.act("WAITMAIN",
            If(self.tag_main_update,
                NextValue(tag_collector, tag_collector + self.tag_main),
                NextState("LAGCHECK")
            )
        )
        # To compensate DDMTD counter roll-over when main is ahead of roll-over
        # and helper is after roll-over
        fsm.act("LEADCHECK",
            If(tag_collector > 0,
                NextValue(tag_collector, tag_collector - (2**N - 1))
            ),
            NextState("UPDATE")
        )
        # To compensate DDMTD counter roll-over when helper is ahead of roll-over
        # and main is after roll-over
        fsm.act("LAGCHECK",
            If(tag_collector < 0,
                NextValue(tag_collector, tag_collector + (2**N - 1))
            ),
            NextState("UPDATE")
        )
        fsm.act("UPDATE",
            NextValue(self.output, tag_collector),
            NextState("IDLE")
        )
