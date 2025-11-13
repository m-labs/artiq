from migen import *

from misoc.interconnect.stream import Endpoint, Buffer
from misoc.cores.duc import complex, RealComplexMultiplier

from artiq.gateware.phaser.register import RO, RW, WO

class Servo(Module):
    def __init__(
        self,
        adc_width,
        adc_channel,
        iq_width,
        iq_sample_pre_cycle,
        a_width,
        iir_coeff_width,
        iir_offset_width,
        iir_fractional_width,
        iir_profiles,
        default_iir_sinks=0,
    ):

        self.iq_sinks = [Record(complex(iq_width)) for _ in range(iq_sample_pre_cycle)]
        self.iq_sources = [
            Record(complex(iq_width)) for _ in range(iq_sample_pre_cycle)
        ]

        iir_layout = [("data", (adc_width, True))]
        self.iir_sinks = [
            Endpoint(iir_layout) for _ in range(adc_channel)
        ]

        # # #

        self.submodules.iir = iir = FirstOrderIIR(
            adc_width,
            a_width,
            iir_coeff_width,
            iir_offset_width,
            iir_fractional_width,
            iir_profiles,
        )
        # Buffer to improve timing
        self.submodules.buffer = buffer = Buffer(iir_layout)

        # Allow IIR to select a different ADC channel as input
        iir_source_sel = Signal(max=adc_channel, reset=default_iir_sinks)
        case = {i: s.connect(buffer.sink) for i, s in enumerate(self.iir_sinks)}
        self.comb += [
            Case(iir_source_sel, case),
            buffer.source.connect(iir.sink)
        ]

        # Always consume IIR outputs to prevent FSM deadlock
        self.comb += iir.source.ack.eq(1) 
        for i in range(iq_sample_pre_cycle):
            mul = RealComplexMultiplier(a_width, iq_width, iq_width)
            self.submodules += mul

            a_r = Signal((a_width, True)) # provide a reset signal for mul.a
            assert len(a_r) == len(mul.a)
            self.comb += mul.a.eq(a_r)
            self.sync += [
                mul.b.eq(self.iq_sinks[i]),
                If(iir.source.stb, a_r.eq(iir.source.data)),
                self.iq_sources[i].eq(mul.p),
            ]

        # Expose register for RTIO
        self.regs = [
            (iir_source_sel, WO),
            (iir.profile_sel, WO),
            (iir.enable, WO),
            (iir.clipped, RO),
        ]

        for cfg, state in zip(iir.configs, iir.states):
            self.regs.extend(
                [
                    (cfg.b0, WO),
                    (cfg.a1, WO),
                    (cfg.b1, WO),
                    (cfg.offset, WO),
                    (state.x1, RO),
                    (state.y1, RW),
                ]
            )

class DSP(Module):
    """
    m = (a + d) * b

    accu_en == 0 => p = 0
    accu_en == 1 => p = m + p
    """

    def __init__(self):
        # Subset of Xilinx DSP48E1 architecture
        self.a = Signal((25, True))
        self.b = Signal((18, True))
        self.c = Signal((48, True))
        self.d = Signal.like(self.a)
        self.p = Signal((48, True))

        self.accu_en = Signal()

        # # #
        
        ad = Signal.like(self.a)
        m = Signal((48, True))
        self.comb += ad.eq(self.a + self.d)
        self.sync += [
            m.eq(ad * self.b),
            If(
                self.accu_en,
                self.p.eq(m + self.p),
            ).Else(
                self.p.eq(0),
            ),
        ]


class FirstOrderIIR(Module):
    """
    A time multiplexed first order IIR filter.
    Uses 1 DSP.

    y0 = clipped((b0*(x0 + offset) + b1*(x1 + offset) + a1 * y1) / a0)

    :param io_width: the sink and source data width
    :param cfg_width: the b0, b1, a1 and offset width
    :param fractional_width: determine the value of a0, a0 = 2 ** fraction_width
    :param n_profile: number of filter configuraiton profiles

    """

    def __init__(
        self,
        input_width,
        output_width,
        coeff_width,
        offset_width,
        fractional_width,
        n_profiles,
    ):
        self.sink = Endpoint([("data", (input_width, True))])
        self.source = Endpoint([("data", (output_width, True))])

        self.profile_sel = Signal(bits_for(n_profiles))
        self.enable = Signal()

        # 0b10 = clip to positive max, 0b01 = clip to negative min, 0b00 = no clipping
        self.clipped = Signal(2)

        self.configs = [
            Record(
                [
                    # a0 is determined by fractional_width
                    ("b0", (coeff_width, True)),
                    ("a1", (coeff_width, True)),
                    ("b1", (coeff_width, True)),
                    ("offset", (offset_width, True)),
                ]
            )
            for _ in range(n_profiles)
        ]

        self.states = [
            Record(
                [
                    ("x1", (len(self.sink.data), True)),
                    ("y1", (len(self.source.data), True)),
                ]
            )
            for _ in range(n_profiles)
        ]

        self.loop_period = 0  # in cycles, calculate later

        # # #

        # Make sure y0 is not always zero due to the fractional shift
        assert (coeff_width - 1) >= fractional_width

        active_config = Record(self.configs[0].layout)
        cfg_read_case = {
            i: NextValue(active_config.raw_bits(), cfg.raw_bits())
            for i, cfg in enumerate(self.configs)
        }

        x0_reg = Signal.like(self.sink.data)
        y0_reg = Signal.like(self.source.data)
        filter_state = Record(self.states[0].layout)
        fs_read_case, fs_write_case = {}, {}
        for i, s in enumerate(self.states):
            fs_read_case[i] = NextValue(filter_state.raw_bits(), s.raw_bits())
            fs_write_case[i] = [
                NextValue(s.x1, x0_reg),
                NextValue(s.y1, y0_reg),
            ]

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        profile_sel_r = Signal.like(self.profile_sel)
        fsm.act(
            "IDLE",
            self.sink.ack.eq(1),
            If(
                self.enable & self.sink.stb,
                Case(self.profile_sel, cfg_read_case),
                Case(self.profile_sel, fs_read_case),
                NextValue(x0_reg, self.sink.data),
                # prevent user changing profile_sel mid FSM and save calculated filter state to the wrong slot
                NextValue(profile_sel_r, self.profile_sel),
                NextState("X0"),
            ),
        )

        self.submodules.dsp = dsp = DSP()
        assert len(dsp.a) >= len(x0_reg) and len(dsp.a) >= len(filter_state.y1)
        assert len(dsp.d) >= len(active_config.offset)
        assert len(dsp.b) >= len(active_config.b0)

        fsm.act(
            "X0",
            dsp.accu_en.eq(1),
            dsp.a.eq(x0_reg),
            dsp.d.eq(active_config.offset),
            dsp.b.eq(active_config.b0),
            NextState("X1"),
        )

        fsm.act(
            "X1",
            dsp.accu_en.eq(1),
            dsp.a.eq(filter_state.x1),
            dsp.d.eq(active_config.offset),
            dsp.b.eq(active_config.b1),
            NextState("Y1"),
        )

        fsm.act(
            "Y1",
            dsp.accu_en.eq(1),
            dsp.a.eq(filter_state.y1),
            dsp.b.eq(active_config.a1),
            NextState("WAIT"),
        )

        # DSP takes two cycles to multiply and accumulate
        # Wait for 1 cycle before getting y0
        fsm.act(
            "WAIT",
            dsp.accu_en.eq(1),
            NextState("Y0_CLIPPING"),
        )

        y0_unclipped = Signal.like(dsp.p)
        self.comb += y0_unclipped.eq(dsp.p >> fractional_width)
        sign_bits = len(y0_unclipped) - len(y0_reg) + 1
        fsm.act(
            "Y0_CLIPPING",
            If(
                y0_unclipped[-sign_bits:] == Replicate(y0_unclipped[-1], sign_bits),
                # all headroom bits match sign bit, in range
                NextValue(y0_reg, y0_unclipped),
                NextValue(self.clipped, 0),
            ).Else(
                # return min or max depending on sign bit
                NextValue(
                    y0_reg,
                    Cat(
                        Replicate(~y0_unclipped[-1], len(y0_unclipped) - sign_bits),
                        Replicate(y0_unclipped[-1], sign_bits),
                    ),
                ),
                NextValue(self.clipped[0], y0_unclipped[-1]),  # clip to negative min
                NextValue(self.clipped[1], ~y0_unclipped[-1]),  # clip to positive max
            ),
            NextState("DONE"),
        )

        fsm.act(
            "DONE",
            # write y0 and x0 into memory for next filter cycle
            Case(profile_sel_r, fs_write_case),
            If(
                self.source.ack,
                self.source.stb.eq(1),
                self.source.data.eq(y0_reg),
                NextState("IDLE"),
            ),
        )

        self.delay = len(fsm.actions)
