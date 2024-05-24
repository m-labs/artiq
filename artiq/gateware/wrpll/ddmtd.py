from migen import *
from migen.genlib.cdc import PulseSynchronizer, MultiReg
from misoc.interconnect.csr import *


class DDMTDSampler(Module):
    def __init__(self, cd_ref, main_clk_se):
        self.ref_beating = Signal()
        self.main_beating = Signal()

        # # #

        ref_clk = Signal()
        self.specials +=[
            # ISERDESE2 can only be driven from fabric via IDELAYE2 (see UG471)
            Instance("IDELAYE2",
                    p_DELAY_SRC="DATAIN",
                    p_HIGH_PERFORMANCE_MODE="TRUE",
                    p_REFCLK_FREQUENCY=208.3,   # REFCLK frequency from IDELAYCTRL
                    p_IDELAY_VALUE=0,

                    i_DATAIN=cd_ref.clk,

                    o_DATAOUT=ref_clk
            ),
            Instance("ISERDESE2",
                    p_IOBDELAY="IFD",   # use DDLY as input
                    p_DATA_RATE="SDR",
                    p_DATA_WIDTH=2,     # min is 2
                    p_NUM_CE=1,

                    i_DDLY=ref_clk,
                    i_CE1=1,
                    i_CLK=ClockSignal("helper"),
                    i_CLKDIV=ClockSignal("helper"),

                    o_Q1=self.ref_beating
            ),
            Instance("ISERDESE2",
                    p_DATA_RATE="SDR",
                    p_DATA_WIDTH=2,     # min is 2
                    p_NUM_CE=1,

                    i_D=main_clk_se,
                    i_CE1=1,
                    i_CLK=ClockSignal("helper"),
                    i_CLKDIV=ClockSignal("helper"),

                    o_Q1=self.main_beating,
            ),
        ]


class DDMTDDeglitcherMedianEdge(Module):
    def __init__(self, counter, input_signal, stable_0_period=100, stable_1_period=100):
        self.tag = Signal(len(counter))
        self.detect = Signal()

        stable_0_counter = Signal(reset=stable_0_period - 1, max=stable_0_period)
        stable_1_counter = Signal(reset=stable_1_period - 1, max=stable_1_period)

        # # #

        # Based on CERN's median edge deglitcher FSM
        # https://white-rabbit.web.cern.ch/documents/Precise_time_and_frequency_transfer_in_a_White_Rabbit_network.pdf (p.72)
        fsm = ClockDomainsRenamer("helper")(FSM(reset_state="WAIT_STABLE_0"))
        self.submodules += fsm

        fsm.act("WAIT_STABLE_0",
            If(stable_0_counter != 0,
                NextValue(stable_0_counter, stable_0_counter - 1)
            ).Else(
                NextValue(stable_0_counter, stable_0_period - 1),
                NextState("WAIT_EDGE")
            ),
            If(input_signal,
                NextValue(stable_0_counter, stable_0_period - 1)
            ),
        )
        fsm.act("WAIT_EDGE",
            If(input_signal,
                NextValue(self.tag, counter),
                NextState("GOT_EDGE")
            )
        )
        fsm.act("GOT_EDGE",
            If(stable_1_counter != 0,
                NextValue(stable_1_counter, stable_1_counter - 1)
            ).Else(
                NextValue(stable_1_counter, stable_1_period - 1),
                self.detect.eq(1),
                NextState("WAIT_STABLE_0")
            ),
            If(~input_signal,
                NextValue(self.tag, self.tag + 1),
                NextValue(stable_1_counter, stable_1_period - 1)
            ),
        )
        

class DDMTD(Module):
    def __init__(self, counter, input_signal):

        # in helper clock domain
        self.h_tag = Signal(len(counter))
        self.h_tag_update = Signal()

        # # #

        deglitcher = DDMTDDeglitcherMedianEdge(counter, input_signal)
        self.submodules += deglitcher

        self.sync.helper += [
            self.h_tag_update.eq(0),
            If(deglitcher.detect,
                self.h_tag_update.eq(1),
                self.h_tag.eq(deglitcher.tag)
               )
        ]