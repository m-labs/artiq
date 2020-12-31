from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer

from misoc.interconnect.csr import *


# See:
# http://www.volkerschatz.com/hardware/clink.html

class Deserializer(Module, AutoCSR):
    def __init__(self, pins):
        self.pll_reset = CSRStorage(reset=1)
        self.pll_locked = CSRStatus()
        self.phase_shift = CSR()
        self.phase_shift_done = CSRStatus(reset=1)
        self.clk_sampled = CSRStatus(7)

        self.q_clk = Signal(7)
        self.q = Signal(7*len(pins.sdi_p))

        self.clock_domains.cd_cl = ClockDomain()
        self.clock_domains.cd_cl7x = ClockDomain()

        # # #

        clk_se = Signal()
        self.specials += Instance("IBUFDS",
            i_I=pins.clk_p, i_IB=pins.clk_n, o_O=clk_se)

        clk_se_iserdes = Signal()
        self.specials += [
            Instance("ISERDESE2",
                p_DATA_WIDTH=7, p_DATA_RATE="SDR",
                p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                p_NUM_CE=1,

                i_D=clk_se,
                o_O=clk_se_iserdes,
                i_CE1=1,
                i_CLKDIV=ClockSignal("cl"), i_RST=ResetSignal("cl"),
                i_CLK=ClockSignal("cl7x"), i_CLKB=~ClockSignal("cl7x"),
                o_Q1=self.q_clk[6],
                o_Q2=self.q_clk[5], o_Q3=self.q_clk[4],
                o_Q4=self.q_clk[3], o_Q5=self.q_clk[2],
                o_Q6=self.q_clk[1], o_Q7=self.q_clk[0]
            )
        ]

        sdi_se = Signal(len(pins.sdi_p))
        for i in range(len(pins.sdi_p)):
            self.specials += [
                Instance("IBUFDS", i_I=pins.sdi_p[i], i_IB=pins.sdi_n[i],
                         o_O=sdi_se[i]),
                Instance("ISERDESE2",
                    p_DATA_WIDTH=7, p_DATA_RATE="SDR",
                    p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                    p_NUM_CE=1,

                    i_D=sdi_se[i],
                    i_CE1=1,
                    i_CLKDIV=ClockSignal("cl"), i_RST=ResetSignal("cl"),
                    i_CLK=ClockSignal("cl7x"), i_CLKB=~ClockSignal("cl7x"),
                    o_Q1=self.q[7*i+6],
                    o_Q2=self.q[7*i+5], o_Q3=self.q[7*i+4],
                    o_Q4=self.q[7*i+3], o_Q5=self.q[7*i+2],
                    o_Q6=self.q[7*i+1], o_Q7=self.q[7*i+0]
                )
            ]

        # CL clock frequency 40-85MHz
        # A7-2 MMCM VCO frequency 600-1440MHz
        # A7-2 PLL  VCO frequency 800-1866MHz
        # with current MMCM settings, CL frequency limited to 40-~68MHz
        # TODO: switch to the PLL, whose VCO range better matches the CL
        # clock frequencies. Needs DRP for dynamic phase shift, see XAPP888.
        pll_reset = Signal(reset=1)
        mmcm_fb = Signal()
        mmcm_locked = Signal()
        mmcm_ps_psdone = Signal()
        cl7x_clk = Signal()
        self.specials += [
            Instance("MMCME2_ADV",
                p_CLKIN1_PERIOD=18.0,
                i_CLKIN1=clk_se_iserdes,
                i_RST=pll_reset,
                i_CLKINSEL=1,  # yes, 1=CLKIN1 0=CLKIN2

                p_CLKFBOUT_MULT_F=21.0,
                p_DIVCLK_DIVIDE=1,
                o_LOCKED=mmcm_locked,

                o_CLKFBOUT=mmcm_fb, i_CLKFBIN=mmcm_fb,

                p_CLKOUT1_USE_FINE_PS="TRUE",
                p_CLKOUT1_DIVIDE=3,
                p_CLKOUT1_PHASE=0.0,
                o_CLKOUT1=cl7x_clk,

                i_PSCLK=ClockSignal(),
                i_PSEN=self.phase_shift.re,
                i_PSINCDEC=self.phase_shift.r,
                o_PSDONE=mmcm_ps_psdone,
            ),
            Instance("BUFR", p_BUFR_DIVIDE="7", i_CLR=~mmcm_locked,
                             i_I=cl7x_clk, o_O=self.cd_cl.clk),
            Instance("BUFIO", i_I=cl7x_clk, o_O=self.cd_cl7x.clk),
            AsyncResetSynchronizer(self.cd_cl, ~mmcm_locked),
        ]
        self.sync += [
            If(self.phase_shift.re, self.phase_shift_done.status.eq(0)),
            If(mmcm_ps_psdone, self.phase_shift_done.status.eq(1))
        ]
        self.specials += MultiReg(self.q_clk, self.clk_sampled.status)

        self.specials += MultiReg(mmcm_locked, self.pll_locked.status)
        pll_reset.attr.add("no_retiming")
        self.sync += pll_reset.eq(self.pll_reset.storage)
