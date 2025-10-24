from collections import namedtuple
import logging
from migen import *
from migen.genlib.coding import Encoder

logger = logging.getLogger(__name__)


# all these are number of bits!
IIRWidths = namedtuple("IIRWidths", [
    "state",        # the signed x and y states of the IIR filter
                    # DSP A input, x state is one bit smaller
                    # due to AD pre-adder, y has full width (25)
    "coeff",        # signed IIR filter coefficients a1, b0, b1 (18)
    "accu",         # IIR accumulator width (48)
    "adc",          # signed ADC data (16)
    "word",         # "word" size to break up DDS profile data (16)
    "asf",          # unsigned amplitude scale factor for DDS (14)
    "shift",        # fixed point scaling coefficient for a1, b0, b1 (log2!) (11)
    "profile",      # profiles per channel (log2!) (5)
    "dly",          # the activation delay
])


DSPWidth = namedtuple("DSPWidth", [
    "padder",       # preadder parameter width (25)
    "mplier",       # multiplier width (25). The preadder feeds into the multiplier
    "mcand",        # multiplicand width (18)
    "accu",         # accumulator width (48)
    "output",       # output width
    "shift",        # fixed point scaling coefficient for truncation
])


def signed(v, w):
    """Convert an unsigned integer ``v`` to it's signed value assuming ``w``
    bits"""
    assert 0 <= v < (1 << w)
    if v & (1 << w - 1):
        v -= 1 << w
    return v


class DSP(Module):
    """Thin abstraction of DSP functionality used here, commonly present,
    and inferrable in FPGAs: multiplier with pre-adder and post-accumulator
    and pipeline registers at every stage."""
    def __init__(self, w, subtract_mode=False, clip=False, signed_output=False):
        self.addend = Signal((w.padder, True))
        self.augend = Signal((w.padder, True))
        self.mcand = Signal((w.mcand, True))
        self.output = Signal((w.output, True))
        self.accu_imm = Signal((w.accu, True))
        self.accu_clr = Signal()
        self.accu_load = Signal()
        self.augend_load = Signal()
        self.mcand_load = Signal()
        self.clip = Signal()

        a = Signal((w.padder, True), reset_less=True)
        d = Signal((w.padder, True), reset_less=True)
        # NOTE:
        # ad factor width is the multiplier width. DSP architecture may force
        # the multiplier width to be the same as the preadder width. With an
        # non-zero augend, care must be taken to ensure that the augend-addend
        # difference does not overflow the width of the ad factor
        ad = Signal((w.mplier, True), reset_less=True)
        b = Signal((w.mcand, True), reset_less=True)
        m = Signal((w.accu, True), reset_less=True)
        p = Signal((w.accu, True), reset_less=True)

        # Equation: output = (((augend' +- addend')' * mcand')' + (output OR accu_imm))'
        #
        # Each prime denotes 1 cycle of delay.
        # Augend and addend should be provided 4 cycles in advance;
        # 3 cycles for mcand, 1 cycle for accu_imm.
        self.sync += [
                a.eq(self.addend),
                If(self.augend_load,
                    d.eq(self.augend)
                ),
                ad.eq(d - a) if subtract_mode else ad.eq(d + a),
                If(self.mcand_load,
                    b.eq(self.mcand),
                ),
                m.eq(ad * b),
                p.eq(p + m),
                If(self.accu_load,
                    # Purely loading an immediate into the accumulator in a
                    # general sense will not infer the P reg.
                    # This can be worked around by forcing m=0.
                    p.eq(self.accu_imm + m),
                ),
                If(self.accu_clr,
                    # inject symmetric rouding constant
                    # p.eq(1 << (w.shift - 1))
                    # but that won't infer P reg, so we just clear
                    # and round down
                    p.eq(0),
                ),
        ]

        self.comb += self.output.eq(p[w.shift:])
        if clip:
            # Bit layout (LSB-MSB): w.shift | w.state - 1 | n_sign - 1 | 1 (sign)
            n_sign = w.accu - w.output - w.shift + 1
            assert n_sign > 1

            # clipping
            if signed_output:
                self.comb += [
                    self.clip.eq(p[-n_sign:] != Replicate(p[-1], n_sign)),
                    If(self.clip,
                        self.output.eq(Cat(Replicate(~p[-1], w.output - 1), p[-1])),
                    ),
                ]
            else:
                self.comb += [
                    self.clip.eq(p[-n_sign:] != 0),
                    If(self.clip,
                        self.output.eq(Replicate(~p[-1], w.output - 1)),
                    ),
                ]


class IIR(Module):
    """Pipelined IIR processor.

    This module implements a multi-channel IIR (infinite impulse response)
    filter processor optimized for synthesis on FPGAs.

    The module is parametrized by passing a ``IIRWidths()`` object, and the
    number of input and output channels respectively. The ``IIRWidths()``
    object will be abbreviated W here.

    It reads ``i_channels`` input channels (typically from an ADC)
    and on each iteration processes the data using a first-order IIR filter.
    At the end of the cycle each the output of the filter together with
    additional data (typically frequency tunning word and phase offset word
    for a DDS) are presented at the ``o_channels`` outputs of the module.

    Profile memory
    ==============

    Each channel can operate using any of its 1 << W.profile profiles.
    The profile data consists of the input ADC channel index (SEL), a delay
    (DLY) for delayed activation of the IIR updates, the three IIR
    coefficients (A1, B0, B1), the input offset (OFFSET), and additional data
    (FTW0, FTW1, and POW). Profile data is stored in a dual-port block RAM that
    can be accessed externally.

    Memory Layout
    -------------

    The profile data is stored sequentially for each channel.
    Each channel has 1 << W.profile profiles available.
    Each profile stores 8 values, each up to W.coeff bits wide, arranged as:
        [POW, B1, FTW0, CFG, OFFSET, A1, FTW1, B0]
    The lower 8 bits of CFG hold the ADC input channel index SEL.
    The subsequent 8 bits hold the IIR activation delay DLY.
    The back memory is 2*W.coeff bits wide and each value pair
    (even and odd address)
    are stored in a single location with the odd address value occupying the
    high bits.

    State memory
    ============

    The filter state consists of the previous ADC input values X1,
    the current ADC input values X0 and the previous output values
    of the IIR filter (Y1). The filter
    state is stored in a dual-port block RAM that can be accessed
    externally.

    Memory Layout
    -------------

    The state memory holds all Y1 values (IIR processor outputs) for all
    profiles of all channels in the lower half ((1 << W.profile) * o_channels
    addresses) and the pairs of old and new ADC input values X1, and X0,
    in the upper half (i_channels addresses each). Each memory location is
    W.state bits wide.

    Real-time control
    =================

    Signals are exposed for each channel:

        * The active profile, PROFILE
        * Whether to perform IIR filter iterations, EN_IIR
        * The RF switch state enabling output from the channel, EN_OUT
        * Whether to perform phase tracking, EN_PT

    Delayed IIR processing
    ======================

    The IIR filter iterations on a given channel are only performed all of the
    following are true:

        * PROFILE, EN_IIR, EN_OUT have not been updated in the within the
          last DLY cycles
        * EN_IIR is asserted
        * EN_OUT is asserted

    DSP design
    ==========

    Typical design at the DSP level. This does not include the description of
    the pipelining or the overall latency involved.

    IIRWidths(state=25, coeff=18, adc=16,
        asf=14, word=16, accu=48, shift=11,
        profile=5, dly=8)

    X0 = ADC * 2^(25 - 1 - 16)
    X1 = X0 delayed by one cycle
    A0 = 2^11
    A0*Y0 = A1*Y1 + B0*(X0 + OFFSET) + B1*(X1 + OFFSET)
    Y1 = Y0 delayed by one cycle
    ASF = Y0 / 2^(25 - 14 - 1)

    ADC: input value from the ADC
    ASF: output amplitude scale factor to DDS
    OFFSET: setpoint
    A0: fixed factor (normalization)
    A1/B0/B1: coefficients (integers)

                    B0 --/-   A0: 2^11
                        18 |         |
    ADC -/-[<<]-/-(+)-/---(x)-(+)-/-[>>]-/-[_/^]-/---[>>]-/- ASF
        16   8  24 | 25 |      |  48 11  37     25 |  10  15
        OFFSET --/-   [z^-1]   ^                 [z^-1]
                24      |      |                   |
                         -(x)-(+)-<-(x)-----<------
                           |         |
                    B1 --/-   A1 --/-
                        18        18

    [<<]: left shift, multiply by 2^n
    [>>]: right shift, divide by 2^n
    (x): multiplication
    (+), (-): addition, subtraction
    [_/^]: clip
    [z^-1]: register, delay by one processing cycle (~1.1 µs)
    --/--: signal with a given bit width always includes a sign bit
    -->--: flow is to the right and down unless otherwise indicated
    """
    def __init__(self, w, i_channels, o_channels, t_cycle, sysclks_per_clk=8):
        self.widths = w
        self.i_channels = i_channels
        self.o_channels = o_channels
        self.t_cycle = t_cycle
        # The number of DDS "sysclk" cycles in each RTIO clock cycle.
        # Note that only 8 is supported. Other ratio can be supported in the
        # condition that I/O update of the DDSes are aligned to its own sysclk
        #
        # Note that the rising edge of I/O update pulses should be synchronous
        # to the corresponding DDS refclk (sysclk/4)
        #
        # Its purpose is to track all DDS phase accumulators w.r.t the sysclk
        # on I/O update pulse
        self.sysclks_per_clk = sysclks_per_clk
        for i, j in enumerate(w):
            assert j > 0, (i, j, w)
        assert w.word <= w.coeff  # same memory
        assert w.state + w.coeff + 3 <= w.accu

        # m_coeff of active profiles should only be accessed externally during
        # ~processing
        self.specials.m_coeff = Memory(
                width=2*w.coeff,  # Cat(pow/ftw/offset, cfg/a/b)
                depth=(4 << w.profile) * o_channels)
        # m_state[x] should only be read externally during ~(shifting | loading)
        # m_state[y] of active profiles should only be read externally during
        # ~processing
        self.specials.m_state = Memory(
                width=w.state,  # y1,x0,x1
                depth=((1 << w.profile) * o_channels) + (2 * i_channels))
        # ctrl should only be updated synchronously
        self.ctrl = [Record([
                ("profile", w.profile),
                ("en_out", 1),
                ("en_iir", 1),
                ("en_pt", 1),
                ("clip", 1),
                ("stb", 1)])
                for i in range(o_channels)]
        # only update during ~loading
        self.adc = [Signal((w.adc, True), reset_less=True)
                for i in range(i_channels)]
        # Cat(ftw0, ftw1, pow, asf)
        # only read externally during ~processing
        self.dds = [Signal(4*w.word, reset_less=True)
                for i in range(o_channels)]
        # perform one IIR iteration, start with loading,
        # then processing, then shifting, end with done
        self.start = Signal()
        # resets the tracked time stamp accumulator, asynchronous to IIR state
        #
        # The accumulator should be reset whenever the servo is disabled.
        self.time_reset = Signal()
        # adc inputs being loaded into RAM (becoming x0)
        self.loading = Signal()
        # processing state data (extracting ftw0/ftw1/pow,
        # computing asf/y0, and storing as y1)
        self.processing = Signal()
        # shifting input state values around (x0 becomes x1)
        self.shifting = Signal()
        # iteration done, the next iteration can be started
        self.done = Signal()

        ###

        # pivot arrays for muxing
        profiles = Array([ch.profile for ch in self.ctrl])
        en_outs = Array([ch.en_out for ch in self.ctrl])
        en_iirs = Array([ch.en_iir for ch in self.ctrl])
        en_pts = Array([ch.en_pt for ch in self.ctrl])
        clips = Array([ch.clip for ch in self.ctrl])

        # Main state machine sequencing the steps of each servo iteration. The
        # module IDLEs until self.start is asserted, and then runs through LOAD,
        # PROCESS and SHIFT in order (see description of corresponding flags
        # above). The steps share the same memory ports, and are executed
        # strictly sequentially.
        #
        # LOAD/SHIFT just read/write one address per cycle; the duration needed
        # to iterate over all channels is determined by counting cycles.
        #
        # The PROCESSing step is split across a three-stage pipeline, where each
        # stage has up to four clock cycles latency. We feed the first stage
        # using the (MSBs of) t_current_step, and, after all channels have been
        # covered, proceed once the pipeline has completely drained.
        self.submodules.fsm = fsm = FSM("IDLE")
        t_current_step = Signal(max=max(i_channels * 2, o_channels * 4))
        t_current_step_clr = Signal()

        # pipeline group activity flags (SR)
        #  0: load from memory
        #  1: compute
        #  2: write to output registers (DDS profiles, clip flags)
        stages_active = Signal(3)
        # scales by DDS number of bits assign to FTW in a single-tone register
        #
        # more higher order bits to track time would not contribute to phase
        # offset calculation
        self.t_global = t_global = Signal(2*w.word)
        fsm.act("IDLE",
                self.done.eq(1),
                t_current_step_clr.eq(1),
                If(self.start,
                    NextState("LOAD")
                )
        )
        fsm.act("LOAD",
                self.loading.eq(1),
                If(t_current_step == i_channels - 1,
                    t_current_step_clr.eq(1),
                    NextValue(stages_active[0], 1),
                    NextState("PROCESS")
                )
        )
        fsm.act("PROCESS",
                self.processing.eq(1),
                # this is technically wasting three cycles
                # (one for setting stages_active, and phase=2,3 with stages_active[2])
                If(stages_active == 0,
                    t_current_step_clr.eq(1),
                    NextState("SHIFT"),
                )
        )
        fsm.act("SHIFT",
                self.shifting.eq(1),
                If(t_current_step == max(o_channels, (i_channels * 2)) - 1,
                    NextValue(t_global, t_global + sysclks_per_clk * t_cycle),  
                    NextState("IDLE")
                )
        )

        self.sync += [
                If(t_current_step_clr,
                    t_current_step.eq(0)
                ).Else(
                    t_current_step.eq(t_current_step + 1)
                ),
                If(self.time_reset, t_global.eq(0))
        ]

        # global pipeline phase (lower two bits of t_current_step)
        pipeline_phase = Signal(2, reset_less=True)
        # pipeline group channel pointer (SR)
        # for each pipeline stage, this is the channel currently being
        # processed
        channel = [Signal(max=o_channels, reset_less=True) for i in range(3)]
        self.comb += Cat(pipeline_phase, channel[0]).eq(t_current_step)
        self.sync += [
            If(pipeline_phase == 3,
                Cat(channel[1:]).eq(Cat(channel[:-1])),
                stages_active[1:].eq(stages_active[:-1]),
                If(channel[0] == o_channels - 1,
                    stages_active[0].eq(0)
                )
            )
        ]

        # pipeline group profile pointer (SR)
        # for each pipeline stage, this is the profile currently being
        # processed
        # FIXME: There introduces a phase offset for all operations
        # Phase tracking DSP may need to account for this (and delay 1 cycle)
        # The channel pointer is out-of-sync at pipeline_phase=0 otherwise
        profile = [Signal(w.profile, reset_less=True) for i in range(2)]
        self.sync += [
            If(pipeline_phase == 0,
                profile[0].eq(profiles[channel[0]]),
                profile[1].eq(profile[0]),
            )
        ]

        m_coeff = self.m_coeff.get_port()
        m_state = self.m_state.get_port(write_capable=True)  # mode=READ_FIRST
        self.specials += m_state, m_coeff

        #
        # Hook up main IIR filter.
        #

        dsp_w = DSPWidth(
            padder=w.state, mplier=w.state, mcand=w.coeff,
            accu=w.accu, output=w.state, shift=w.shift)
        dsp = DSP(dsp_w, clip=True)
        self.submodules += dsp

        offset_clr = Signal()
        self.comb += [
                m_coeff.adr.eq(Cat(pipeline_phase, profile[0],
                    Mux(pipeline_phase == 0, channel[1], channel[0]))),
                dsp.augend[-w.coeff - 1:].eq(Mux(offset_clr, 0,
                    Cat(m_coeff.dat_r[:w.coeff], m_coeff.dat_r[w.coeff - 1])
                )),
                dsp.mcand_load.eq(1),
                dsp.mcand.eq(m_coeff.dat_r[w.coeff:]),
                dsp.addend.eq(m_state.dat_r),
                Case(pipeline_phase, {
                    0: dsp.accu_clr.eq(1),
                    2: [
                        offset_clr.eq(1),
                        dsp.augend_load.eq(1)
                    ],
                    3: dsp.augend_load.eq(1)
                })
        ]


        #
        # Arbitrate state memory access between steps.
        #

        # selected adc and profile delay (combinatorial from dat_r)
        # both share the same coeff word (sel in the lower 8 bits)
        sel_profile = Signal(max=i_channels)
        dly_profile = Signal(w.dly)
        assert i_channels <= 1 << 8
        assert 8 + w.dly <= w.coeff

        # latched adc selection
        sel = Signal(max=i_channels, reset_less=True)
        # iir enable SR
        en = Signal(2, reset_less=True)

        # Memory for values required to track the phase accumulator.
        # Arranged as the following:
        # T_REF * (1 << w.profile) * o_channels
        # [PREV_FTW, PREV_ACCU] * o_channels
        #
        # PREV_ACCU is the phase accumulator in the previous iteration.
        # T_REF is the fiducial timestamp.
        # PREV_FTW is the FTW in the previous iteration.
        # Offset 3 is unused, to avoid maintaining a separate counter.
        self.specials.m_phase = Memory(2*w.word, ((1 << w.profile) + 2) * o_channels)

        m_phase = self.m_phase.get_port(write_capable=True, mode=READ_FIRST)
        self.specials += m_phase

        # muxing
        ddss = Array(self.dds)
        next_accu_neg = Signal(32)

        self.comb += [
                sel_profile.eq(m_coeff.dat_r[w.coeff:]),
                dly_profile.eq(m_coeff.dat_r[w.coeff + 8:]),
                If(self.shifting,
                    # There can be more steps than necessary to shift
                    # This only causes truncation of address, and can only
                    # cause rewrites of the same entry by the same value
                    m_state.adr.eq(t_current_step + ((1 << w.profile) * o_channels)),
                    m_state.dat_w.eq(m_state.dat_r),
                    m_state.we.eq(t_current_step[0]),

                    # Same as the above, but o_channels may not be a power of 2
                    # Then there can be an address of out of bound issue
                    m_phase.adr.eq(0 | (t_current_step << 1) + ((1 << w.profile) * o_channels),),
                    m_phase.we.eq(t_current_step < o_channels),
                    m_phase.dat_w.eq(ddss[t_current_step][:2 * w.word]),
                ),
                If(self.loading,
                    m_state.adr.eq((t_current_step << 1) + ((1 << w.profile) * o_channels)),
                    m_state.dat_w[-w.adc - 1:-1].eq(Array(self.adc)[t_current_step]),
                    m_state.dat_w[-1].eq(m_state.dat_w[-2]),
                    m_state.we.eq(1)
                ),
                If(self.processing,
                    m_state.adr.eq(Array([
                        # write back new y
                        Cat(profile[1], channel[2]),
                        # read old y
                        Cat(profile[0], channel[0]),
                        # read x0 (recent)
                        0 | (sel_profile << 1) + ((1 << w.profile) * o_channels),
                        # read x1 (old)
                        1 | (sel << 1) + ((1 << w.profile) * o_channels),
                    ])[pipeline_phase]),
                    m_state.dat_w.eq(dsp.output),
                    m_state.we.eq((pipeline_phase == 0) & stages_active[2] & en[1]),

                    m_phase.adr.eq(Array([
                        # read profile-specific fiducial time stamp
                        # Using profile[0] will not work. See the FIXME above.
                        Cat(profiles[channel[0]], channel[0]),
                        # read FTW from the previous iteration
                        0 | (channel[0] << 1) + ((1 << w.profile) * o_channels),
                        # read tracked phase accumulator
                        1 | (channel[0] << 1) + ((1 << w.profile) * o_channels),
                        # write back phase accumulator
                        1 | (channel[0] << 1) + ((1 << w.profile) * o_channels),
                    ])[pipeline_phase]),
                    m_phase.dat_w.eq(next_accu_neg),
                    m_phase.we.eq((pipeline_phase == 3) & stages_active[0]),
                )
        ]

        #
        # Compute auxiliary signals (delayed servo enable, clip indicators, etc.).
        #

        # internal channel delay counters
        dlys = Array([Signal(w.dly)
            for i in range(o_channels)])
        self._dlys = dlys  # expose for debugging only

        for i in range(o_channels):
            self.sync += [
                    # (profile != profile_old) | ~en_out
                    If(self.ctrl[i].stb,
                        dlys[i].eq(0),
                    )
            ]

        # latched channel delay
        dly = Signal(w.dly, reset_less=True)
        # latched channel en_out
        en_out = Signal(reset_less=True)
        # latched channel en_iir
        en_iir = Signal(reset_less=True)

        self.sync += [
            Case(pipeline_phase, {
                0: [
                    dly.eq(dlys[channel[0]]),
                    en_out.eq(en_outs[channel[0]]),
                    en_iir.eq(en_iirs[channel[0]]),
                    If(stages_active[2] & en[1] & dsp.clip,
                        clips[channel[2]].eq(1)
                    )
                ],
                2: [
                    en[0].eq(0),
                    en[1].eq(en[0]),
                    sel.eq(sel_profile),
                    If(stages_active[0] & en_out,
                        If(dly != dly_profile,
                            dlys[channel[0]].eq(dly + 1)
                        ).Elif(en_iir,
                            en[0].eq(1)
                        )
                    )
                ],
            }),
        ]

        # The DSP calculates this on EN_PT:
        # POW_TOTAL = POW + (t - t_ref) * FTW - ACCU
        #
        # The POW adjustment calculation will be unused if ~EN_PT
        # i.e. POW_TOTAL = POW
        #
        # It decomposes into 4 steps:
        # P0 = ((t[:16] - t_ref[:16]) * FTW[:16]) - ACCU
        # P1 = ((t[16:] - t_ref[16:]) * FTW[:16]) + P0[16:]
        # P2 = ((t[:16] - t_ref[:16]) * FTW[16:]) + P1
        # POW_TOTAL = (1 - 0) * POW + (P2 or 0)
        #
        # Each input corresponds to the augend, addend, mcand variables and
        # the accumulator input respectively.
        #
        # Pipeline table:
        #
        # | Signals \ Pipeline phase (stage) |    1 (0)   |    2 (0)   |    3 (0)   |   0 (1)  |   1 (1)  | 2 (1) |  3 (1)  |   0 (2)   |
        # |:--------------------------------:|:----------:|:----------:|:----------:|:--------:|:--------:|:-----:|:-------:|:---------:|
        # |              Augend              |   t[:16]   |   t[16:]   |   t[:16]   |     1    |    ---   |  ---  |   ---   |    ---    |
        # |              Addend              | t_ref[:16] | t_ref[16:] | t_ref[:16] |     0    |    ---   |  ---  |   ---   |    ---    |
        # |           Multiplicand           |     ---    |  FTW[:16]  |  FTW[:16]  | FTW[16:] |    POW   |  ---  |   ---   |    ---    |
        # |            Accumulator           |     ---    |     ---    |     ---    |   -ACCU  | P0 >> 16 |   P1  | P2 OR 0 |    ---    |
        # |              Output              |     ---    |     ---    |     ---    |    ---   |    P0    |   P1  |    P2   | POW_TOTAL |

        phase_dsp_w = DSPWidth(
            padder=w.word+1, mplier=w.word+2, mcand=w.word+1,
            accu=w.accu, output=w.accu, shift=0)
        phase_dsp = DSP(phase_dsp_w, subtract_mode=True)
        self.submodules += phase_dsp

        self.comb += [
            phase_dsp.mcand.eq(m_coeff.dat_r[:16]),
            phase_dsp.augend_load.eq(1),
        ]

        t_ref = Signal(2*w.word)

        accu_neg = Signal(2*w.word)
        self.comb += next_accu_neg.eq(m_phase.dat_r - accu_neg)
        self.sync += accu_neg.eq(next_accu_neg)

        # pipeline time multiplexed DSP access
        self.comb += [
            Case(pipeline_phase, {
                0: [
                    If(stages_active[1],
                        phase_dsp.augend.eq(1),
                        phase_dsp.addend.eq(0),
                        phase_dsp.mcand_load.eq(1),  # ftw1
                        phase_dsp.accu_load.eq(1),  # phase accumulator (-ve)
                        phase_dsp.accu_imm.eq(accu_neg),
                    ),
                ],
                1: [
                    If(stages_active[0],
                        phase_dsp.augend.eq(t_global[:w.word]),
                        phase_dsp.addend.eq(m_phase.dat_r[:w.word]),
                    ),
                    If(stages_active[1],
                        phase_dsp.mcand_load.eq(1),  # pow
                        phase_dsp.accu_load.eq(1),
                        phase_dsp.accu_imm.eq(phase_dsp.output[w.word:]),
                    ),
                ],
                2: [
                    If(stages_active[0],
                        phase_dsp.mcand_load.eq(1),  # ftw0
                        phase_dsp.augend.eq(t_global[w.word:]),
                        phase_dsp.addend.eq(t_ref[w.word:]),
                    ),
                ],
                3: [
                    If(stages_active[0],
                        phase_dsp.augend.eq(t_global[:w.word]),
                        phase_dsp.addend.eq(t_ref[:w.word]),
                    ),
                    If(stages_active[1],
                        phase_dsp.accu_load.eq(~en_pts[channel[1]]),
                        phase_dsp.accu_imm.eq(0),
                    ),
                ],
            })
        ]

        #
        # Update DDS profile with FTW/POW/ASF.
        # Stage 1 loads the FTW.
        # Stage 2 writes the ASF computed by the IIR filter, and the computed
        # POW from the phase tracking DSP.
        #

        self.sync += [
            Case(pipeline_phase, {
                0: [
                    If(stages_active[1],
                        ddss[channel[1]][w.word:2 * w.word].eq(m_coeff.dat_r),  # ftw1
                    ),
                    If(stages_active[2],
                        ddss[channel[2]][2*w.word:3*w.word].eq(phase_dsp.output),  # pow
                    ),
                ],
                1: [
                    If(stages_active[0],
                        t_ref.eq(m_phase.dat_r),
                    ),
                    If(stages_active[2],
                        ddss[channel[2]][3*w.word:].eq(  # asf
                            m_state.dat_r[w.state - w.asf - 1:w.state - 1])
                    )
                ],
                2: [
                    If(stages_active[0],
                        ddss[channel[0]][:w.word].eq(m_coeff.dat_r),  # ftw0
                        accu_neg.eq(m_phase.dat_r * t_cycle * sysclks_per_clk),
                    ),
                ],
                3: [
                ],
            }),
        ]

    def _coeff(self, channel, profile, coeff):
        """Return ``high_word``, ``address`` and bit ``mask`` for the
        storage of coefficient name ``coeff`` in profile ``profile``
        of channel ``channel``.

        ``high_word`` determines whether the coefficient is stored in the high
        or low part of the memory location.
        """
        w = self.widths
        addr = "pow b1 ftw0 cfg offset a1 ftw1 b0".split().index(coeff)
        coeff_addr = ((channel << w.profile + 2) | (profile << 2) |
                (addr >> 1))
        mask = (1 << w.coeff) - 1
        return addr & 1, coeff_addr, mask

    def set_coeff(self, channel, profile, coeff, value):
        """Set the coefficient value.

        Note that due to two coefficiddents sharing a single memory
        location, only one coefficient update can be effected to a given memory
        location per simulation clock cycle.
        """
        w = self.widths
        word, addr, mask = self._coeff(channel, profile, coeff)
        val = yield self.m_coeff[addr]
        if word:
            val = (val & mask) | ((value & mask) << w.coeff)
        else:
            val = (value & mask) | (val & (mask << w.coeff))
        yield self.m_coeff[addr].eq(val)

    def get_coeff(self, channel, profile, coeff):
        """Get a coefficient value."""
        w = self.widths
        word, addr, mask = self._coeff(channel, profile, coeff)
        val = yield self.m_coeff[addr]
        if word:
            val >>= w.coeff
        else:
            val &= mask
        if coeff in "offset a1 b0 b1".split():
            val = signed(val, w.coeff)
        elif coeff in "ftw0 ftw1 pow".split():
            val = val & ((1 << w.word) - 1)
        return val

    def set_state(self, channel, val, profile=None, coeff="y1"):
        """Set a state value."""
        w = self.widths
        if coeff == "y1":
            assert profile is not None
            yield self.m_state[profile | (channel << w.profile)].eq(val)
        elif coeff == "x0":
            assert profile is None
            yield self.m_state[(channel << 1) |
                    ((1 << w.profile) * self.o_channels)].eq(val)
        elif coeff == "x1":
            assert profile is None
            yield self.m_state[1 | (channel << 1) |
                    ((1 << w.profile) * self.o_channels)].eq(val)
        else:
            raise ValueError("no such state", coeff)

    def get_state(self, channel, profile=None, coeff="y1"):
        """Get a state value."""
        w = self.widths
        if coeff == "y1":
            val = yield self.m_state[profile | (channel << w.profile)]
        elif coeff == "x0":
            val = yield self.m_state[(channel << 1) |
                    ((1 << w.profile) * self.o_channels)]
        elif coeff == "x1":
            val = yield self.m_state[1 | (channel << 1) |
                    ((1 << w.profile) * self.o_channels)]
        else:
            raise ValueError("no such state", coeff)
        return signed(val, w.state)

    def set_fiducial_timestamp(self, channel, profile, val):
        w = self.widths
        yield self.m_phase[profile | (channel << w.profile)].eq(val)

    def get_fiducial_timestamp(self, channel, profile):
        w = self.widths
        val = yield self.m_phase[profile | (channel << w.profile)]
        return val

    def set_prev_ftw(self, channel, val):
        w = self.widths
        yield self.m_phase[(channel << 1) +
                    ((1 << w.profile) * self.o_channels)].eq(val)

    def get_prev_ftw(self, channel):
        w = self.widths
        val = yield self.m_phase[(channel << 1) +
                    ((1 << w.profile) * self.o_channels)]
        return val

    def set_phase_accumulator(self, channel, val):
        w = self.widths
        yield self.m_phase[1 | (channel << 1) +
                    ((1 << w.profile) * self.o_channels)].eq(val)

    def get_phase_accumulator(self, channel):
        w = self.widths
        val = yield self.m_phase[1 | (channel << 1) +
                    ((1 << w.profile) * self.o_channels)]
        return val

    def fast_iter(self):
        """Perform a single processing iteration."""
        assert (yield self.done)
        yield self.start.eq(1)
        yield
        yield self.start.eq(0)
        yield
        while not (yield self.done):
            yield

    def check_iter(self):
        """Perform a single processing iteration while verifying
        the behavior."""
        w = self.widths

        while not (yield self.done):
            yield

        yield self.start.eq(1)
        yield
        yield self.start.eq(0)
        yield
        assert not (yield self.done)
        assert (yield self.loading)
        while (yield self.loading):
            yield

        x0s = []
        # check adc loading
        for i in range(self.i_channels):
            v_adc = signed((yield self.adc[i]), w.adc)
            x0 = yield from self.get_state(i, coeff="x0")
            x0s.append(x0)
            assert v_adc << (w.state - w.adc - 1) == x0, (hex(v_adc), hex(x0))
            logger.debug("adc[%d] adc=%x x0=%x", i, v_adc, x0)

        data = []
        # predict output
        for i in range(self.o_channels):
            j = yield self.ctrl[i].profile
            en_iir = yield self.ctrl[i].en_iir
            en_out = yield self.ctrl[i].en_out
            en_pt = yield self.ctrl[i].en_pt
            dly_i = yield self._dlys[i]
            logger.debug("ctrl[%d] profile=%d en_iir=%d en_out=%d dly=%d",
                    i, j, en_iir, en_out, dly_i)

            cfg = yield from self.get_coeff(i, j, "cfg")
            k_j = cfg % self.i_channels
            dly_j = (cfg >> 8) & 0xff
            logger.debug("cfg[%d,%d] sel=%d dly=%d", i, j, k_j, dly_j)

            en = en_iir & en_out & (dly_i >= dly_j)
            logger.debug("en[%d,%d] %d", i, j, en)

            offset = yield from self.get_coeff(i, j, "offset")
            offset <<= w.state - w.coeff - 1
            a1 = yield from self.get_coeff(i, j, "a1")
            b0 = yield from self.get_coeff(i, j, "b0")
            b1 = yield from self.get_coeff(i, j, "b1")
            logger.debug("coeff[%d,%d] offset=%#x a1=%#x b0=%#x b1=%#x",
                    i, j, offset, a1, b0, b1)

            ftw0 = yield from self.get_coeff(i, j, "ftw0")
            ftw1 = yield from self.get_coeff(i, j, "ftw1")
            pow = yield from self.get_coeff(i, j, "pow")
            logger.debug("dds[%d,%d] ftw0=%#x ftw1=%#x pow=%#x",
                    i, j, ftw0, ftw1, pow)

            y1 = yield from self.get_state(i, j, "y1")
            x1 = yield from self.get_state(k_j, coeff="x1")
            x0 = yield from self.get_state(k_j, coeff="x0")
            logger.debug("state y1[%d,%d]=%#x x0[%d]=%#x x1[%d]=%#x",
                    i, j, y1, k_j, x0, k_j, x1)

            p = (0*(1 << w.shift - 1) + a1*(y1 + 0) +
                    b0*(x0 + offset) + b1*(x1 + offset))
            out = p >> w.shift
            y0 = min(max(0, out), (1 << w.state - 1) - 1)
            logger.debug("dsp[%d,%d] p=%#x out=%#x y0=%#x",
                    i, j, p, out, y0)

            if en_pt:
                prev_ftw = yield from self.get_prev_ftw(i)
                accu_neg = yield from self.get_phase_accumulator(i)
                fiducial_ts = yield from self.get_fiducial_timestamp(i, j)
                t_global = yield self.t_global
                logger.debug("dds[%d,%d] prev_ftw=%#x accu_neg=%#x fiducial_ts=%#x global_ts=%#x",
                        i, j, prev_ftw, accu_neg, fiducial_ts, t_global)

                accu_neg -= prev_ftw * self.t_cycle * self.sysclks_per_clk
                target_pow = ((ftw1 << 16) | ftw0) * (t_global - fiducial_ts)
                pow += ((target_pow + accu_neg) >> 16)
                pow &= ((1 << 16) - 1)

            if not en:
                y0 = y1
            data.append((ftw0, ftw1, pow, y0, x1, x0))

        # wait for output
        assert (yield self.processing)
        while (yield self.processing):
            yield

        assert (yield self.shifting)
        while (yield self.shifting):
            yield

        # check x shifting
        for i, x0 in enumerate(x0s):
            x1 = yield from self.get_state(i, coeff="x1")
            assert x1 == x0, (hex(x1), hex(x0))
            logger.debug("adc[%d] x0=%x x1=%x", i, x0, x1)

        # check new state
        for i in range(self.o_channels):
            j = yield self.ctrl[i].profile
            logger.debug("ch[%d] profile=%d", i, j)
            y1 = yield from self.get_state(i, j, "y1")
            ftw0, ftw1, pow, y0, x1, x0 = data[i]
            assert y1 == y0, (hex(y1), hex(y0))

        # check dds output
        for i in range(self.o_channels):
            ftw0, ftw1, pow, y0, x1, x0 = data[i]
            asf = y0 >> (w.state - w.asf - 1)
            dds = (ftw0 | (ftw1 << w.word) |
                    (pow << 2*w.word) | (asf << 3*w.word))
            dds_state = yield self.dds[i]
            logger.debug("ch[%d] dds_state=%#x dds=%#x", i, dds_state, dds)
            assert dds_state == dds, [hex(_) for _ in
                    (dds_state, asf, pow, ftw1, ftw0)]

        assert (yield self.done)
        return data
