from migen import *
from migen.genlib.cdc import PulseSynchronizer, MultiReg
from migen.genlib.fsm import FSM
from misoc.interconnect.csr import *


class DDMTDSamplerExtFF(Module):
    def __init__(self, ddmtd_inputs):
        # TODO: s/h timing at FPGA pads
        if hasattr(ddmtd_inputs, "rec_clk"):
            self.rec_clk = ddmtd_inputs.rec_clk
        else:
            self.rec_clk = Signal()
            self.specials += Instance("IBUFDS",
                i_I=ddmtd_inputs.rec_clk_p, i_IB=ddmtd_inputs.rec_clk_n,
                o_O=self.rec_clk)
        if hasattr(ddmtd_inputs, "main_xo"):
            self.main_xo = ddmtd_inputs.main_xo
        else:
            self.main_xo = Signal()
            self.specials += Instance("IBUFDS",
                i_I=ddmtd_inputs.main_xo_p, i_IB=ddmtd_inputs.main_xo_n,
                o_O=self.main_xo)


class DDMTDSamplerGTP(Module):
    def __init__(self, gtp, main_xo_pads):
        self.rec_clk = Signal()
        self.main_xo = Signal()

        # Getting the main XO signal from IBUFDS_GTE2 is problematic because
        # the transceiver PLL craps out if an improper clock signal is applied,
        # so we are disabling the buffer until the clock is stable.
        main_xo_se = Signal()
        self.specials += [
            Instance("IBUFDS",
                i_I=main_xo_pads.p, i_IB=main_xo_pads.n,
                o_O=main_xo_se),
            Instance("FD", i_C=ClockSignal("helper"),
                i_D=gtp.cd_rtio_rx0.clk, o_Q=self.rec_clk,
                attr={("DONT_TOUCH", "TRUE")}),
            Instance("FD", i_C=ClockSignal("helper"),
                i_D=main_xo_se, o_Q=self.main_xo,
                attr={("IOB", "TRUE")}),
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
        self.tag_helper = Signal(N)
        self.tag_helper_update = Signal()
        self.tag_main = Signal(N)
        self.tag_main_update = Signal()

        self.output = Signal(N)
        self.output_update = Signal(N)

        # # #

        fsm = FSM()
        self.submodules += fsm

        tag_collector = Signal(N)
        fsm.act("IDLE",
            If(self.tag_main_update & self.tag_helper_update,
                NextValue(tag_collector, 0),
                NextState("IDLE")
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
                NextState("IDLE")
            )
        )
        fsm.act("WAITMAIN",
            If(self.tag_main_update,
                NextValue(tag_collector, tag_collector + self.tag_main),
                NextState("IDLE")
            )
        )
        self.sync += [
            self.output_update.eq(0),
            If(self.tag_helper_update,
                self.output_update.eq(1),
                self.output.eq(tag_collector)
            )
        ]
