from migen import *
from migen.genlib.cdc import MultiReg

from misoc.interconnect.csr import *


# This code assumes 125MHz system clock and 150MHz RTIO frequency.

class SiPhaser7Series(Module, AutoCSR):
    def __init__(self, si5324_clkin, si5324_clkout_fabric):
        self.switch_clocks = CSRStorage()
        self.phase_shift = CSR()
        self.phase_shift_done = CSRStatus(reset=1)
        self.sample_result = CSRStatus()

        # 125MHz system clock to 150MHz. VCO @ 625MHz.
        # Used to provide a startup clock to the transceiver through the Si,
        # we do not use the crystal reference so that the PFD (f3) frequency
        # can be high.
        mmcm_freerun_fb = Signal()
        mmcm_freerun_output = Signal()
        self.specials += \
            Instance("MMCME2_BASE",
                p_CLKIN1_PERIOD=1e9/125e6,
                i_CLKIN1=ClockSignal("sys"),
                i_RST=ResetSignal("sys"),

                p_CLKFBOUT_MULT_F=6.0, p_DIVCLK_DIVIDE=1,

                o_CLKFBOUT=mmcm_freerun_fb, i_CLKFBIN=mmcm_freerun_fb,

                p_CLKOUT0_DIVIDE_F=5.0, o_CLKOUT0=mmcm_freerun_output,
            )
        
        # 150MHz to 150MHz with controllable phase shift, VCO @ 1200MHz.
        # Inserted between CDR and output to Si, used to correct 
        # non-determinstic skew of Si5324.
        mmcm_ps_fb = Signal()
        mmcm_ps_output = Signal()
        mmcm_ps_psdone = Signal()
        self.specials += \
            Instance("MMCME2_ADV",
                p_CLKIN1_PERIOD=1e9/150e6,
                i_CLKIN1=ClockSignal("rtio_rx0"),
                i_RST=ResetSignal("rtio_rx0"),
                i_CLKINSEL=1,  # yes, 1=CLKIN1 0=CLKIN2

                p_CLKFBOUT_MULT_F=8.0,
                p_CLKOUT0_DIVIDE_F=8.0,
                p_DIVCLK_DIVIDE=1,

                o_CLKFBOUT=mmcm_ps_fb, i_CLKFBIN=mmcm_ps_fb,

                p_CLKOUT0_USE_FINE_PS="TRUE",
                o_CLKOUT0=mmcm_ps_output,

                i_PSCLK=ClockSignal(),
                i_PSEN=self.phase_shift.re,
                i_PSINCDEC=self.phase_shift.r,
                o_PSDONE=mmcm_ps_psdone,
            )
        self.sync += [
            If(self.phase_shift.re, self.phase_shift_done.status.eq(0)),
            If(mmcm_ps_psdone, self.phase_shift_done.status.eq(1))
        ]

        si5324_clkin_se = Signal()
        self.specials += [
            Instance("BUFGMUX",
                i_I0=mmcm_freerun_output,
                i_I1=mmcm_ps_output,
                i_S=self.switch_clocks.storage,
                o_O=si5324_clkin_se
            ),
            Instance("OBUFDS",
                i_I=si5324_clkin_se,
                o_O=si5324_clkin.p, o_OB=si5324_clkin.n
            )
        ]

        si5324_clkout_se = Signal()
        self.specials += \
            Instance("IBUFDS",
                p_DIFF_TERM="TRUE", p_IBUF_LOW_PWR="TRUE",
                i_I=si5324_clkout_fabric.p, i_IB=si5324_clkout_fabric.n,
                o_O=si5324_clkout_se),
        
        clkout_sample1 = Signal()  # IOB register
        self.sync.rtio_rx0 += clkout_sample1.eq(si5324_clkout_se)
        self.specials += MultiReg(clkout_sample1, self.sample_result.status)

        # expose MMCM outputs - used for clock constraints
        self.mmcm_freerun_output = mmcm_freerun_output
        self.mmcm_ps_output = mmcm_ps_output
