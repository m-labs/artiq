from migen import *
from migen.genlib.cdc import PulseSynchronizer, MultiReg
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

        # Getting the main XO signal from IBUFDS_GTE2 is problematic because:
        # 1. the clock gets divided by 2
        # 2. the transceiver PLL craps out if an improper clock signal is applied,
        # so we are disabling the buffer until the clock is stable.
        # 3. UG482 says "The O and ODIV2 outputs are not phase matched to each other",
        # which may or may not be a problem depending on what it actually means.
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


class DDMTDEdgeDetector(Module):
    def __init__(self, input_signal):
        self.rising = Signal()

        history = Signal(4)
        deglitched = Signal()
        self.sync.helper += history.eq(Cat(history[1:], input_signal))
        self.comb += deglitched.eq(input_signal | history[0] | history[1] | history[2] | history[3])

        deglitched_r = Signal()
        self.sync.helper += [
            deglitched_r.eq(deglitched),
            self.rising.eq(deglitched & ~deglitched_r)
        ]


class DDMTD(Module, AutoCSR):
    def __init__(self, counter, input_signal):
        self.arm = CSR()
        self.tag = CSRStatus(len(counter))

        # in helper clock domain
        self.h_tag = Signal(len(counter))
        self.h_tag_update = Signal()

        # # #

        ed = DDMTDEdgeDetector(input_signal)
        self.submodules += ed

        self.sync.helper += [
            self.h_tag_update.eq(0),
            If(ed.rising,
                self.h_tag_update.eq(1),
                self.h_tag.eq(counter)
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
