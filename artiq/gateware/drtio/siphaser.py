from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer

from misoc.interconnect.csr import *


# This code assumes 125/62.5MHz reference clock and 125MHz or 150MHz RTIO
# frequency.

class SiPhaser7Series(Module, AutoCSR):
    def __init__(self, si5324_clkin, rx_synchronizer,
                 ref_clk=None, ref_div2=False, ultrascale=False, rtio_clk_freq=150e6):
        self.switch_clocks = CSRStorage()
        self.phase_shift = CSR()
        self.phase_shift_done = CSRStatus(reset=1)
        self.error = CSR()

        assert rtio_clk_freq in (125e6, 150e6)

        # 125MHz/62.5MHz reference clock to 125MHz/150MHz. VCO @ 750MHz.
        # Used to provide a startup clock to the transceiver through the Si,
        # we do not use the crystal reference so that the PFD (f3) frequency
        # can be high.
        mmcm_freerun_fb = Signal()
        mmcm_freerun_output_raw = Signal()
        self.specials += \
            Instance("MMCME2_BASE",
                p_CLKIN1_PERIOD=16.0 if ref_div2 else 8.0,
                i_CLKIN1=ClockSignal("sys") if ref_clk is None else ref_clk,
                i_RST=ResetSignal("sys") if ref_clk is None else 0,

                p_CLKFBOUT_MULT_F=12.0 if ref_div2 else 6.0,
                p_DIVCLK_DIVIDE=1,

                o_CLKFBOUT=mmcm_freerun_fb, i_CLKFBIN=mmcm_freerun_fb,

                p_CLKOUT0_DIVIDE_F=750e6/rtio_clk_freq,
                o_CLKOUT0=mmcm_freerun_output_raw,
            )
        if ultrascale:
            mmcm_freerun_output = Signal()
            self.specials += Instance("BUFG", i_I=mmcm_freerun_output_raw, o_O=mmcm_freerun_output)
        else:
            mmcm_freerun_output = mmcm_freerun_output_raw

        # 125MHz/150MHz to 125MHz/150MHz with controllable phase shift,
        # VCO @ 1000MHz/1200MHz.
        # Inserted between CDR and output to Si, used to correct
        # non-determinstic skew of Si5324.
        mmcm_ps_fb = Signal()
        mmcm_ps_output = Signal()
        mmcm_ps_psdone = Signal()
        self.specials += \
            Instance("MMCME2_ADV",
                p_CLKIN1_PERIOD=1e9/rtio_clk_freq,
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

        # The RX synchronizer is tested for setup/hold violations by feeding it a
        # toggling pattern and checking that the same toggling pattern comes out.
        toggle_in = Signal()
        self.sync.rtio_rx0 += toggle_in.eq(~toggle_in)
        toggle_out = rx_synchronizer.resync(toggle_in)

        toggle_out_expected = Signal()
        self.sync.rtio += toggle_out_expected.eq(~toggle_out)

        error = Signal()
        error_clear = PulseSynchronizer("sys", "rtio")
        self.submodules += error_clear
        self.sync.rtio += [
            If(toggle_out != toggle_out_expected, error.eq(1)),
            If(error_clear.o, error.eq(0))
        ]
        self.specials += MultiReg(error, self.error.w)
        self.comb += error_clear.i.eq(self.error.re)

        # expose MMCM outputs - used for clock constraints
        self.mmcm_freerun_output = mmcm_freerun_output
        self.mmcm_ps_output = mmcm_ps_output
