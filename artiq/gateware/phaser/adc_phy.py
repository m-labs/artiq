from migen import *
from migen.genlib.io import DifferentialInput

from misoc.interconnect.stream import Endpoint

from artiq.gateware.phaser.dac_phy import TxSerializer

from math import ceil
from types import SimpleNamespace

ADC_CAHNNELS = 2
ADC_DATA_WIDTH = 16
ADC_LAYOUT = [("data", (ADC_DATA_WIDTH, True))]

# From 232316fc - ADC TIMING CHARACTERISTICS table (ns)
MIN_SCK_PERIOD = 9.4
MIN_CNVN_H_TIME = 25  # CNVN high time
MIN_CNVN2SCK_TIME = 9.5  # Time between CNVN filing edge and SCK begin (dcnvsckl)
MIN_SCK2NEXT_CNVN_H_TIME = 19.1  # Time between last SCK failing edge and next CNVN


class LTC2323PHY(Module):
    """
    LTC2320 PHY designed for 125 MHz sys clock

    Supports:
    - Two channels sampling at 4.8 MSPS
    - Generate 100 MHz SCK
    """

    def __init__(self, pins, sys_clk_freq):
        self.sources = [Endpoint(ADC_LAYOUT) for _ in range(ADC_CAHNNELS)]

        self.sample_period = 0 # in cycles, calculate later
        # # #

        # CNVN and SCK generation:
        # - CNVN state takes 48 ns = 10 ns CNVN=0 + 25 ns CNVN=1 + 10 ns CNVN=0 + 3 ns CNVN=0 padding to align to 8 ns sys clock
        # - SCK state takes 160 ns = 16 * 10 ns SCK
        # - One sampling cycle = 160 + 48 ns = 208 ns => 4.8 MSPS
        sys_clk_period = 1e9 / sys_clk_freq
        self.sck_period = 10
        assert sys_clk_freq == 125e6
        assert self.sck_period >= MIN_SCK_PERIOD

        t_sck_end_2_cnvn_h = ceil(MIN_SCK2NEXT_CNVN_H_TIME - self.sck_period)
        t_cnvn_h = ceil(MIN_CNVN_H_TIME)
        cnvn_state_duration = ceil(
            (t_sck_end_2_cnvn_h + t_cnvn_h + MIN_CNVN2SCK_TIME) / sys_clk_period
        )
        cnvn = ((1 << t_cnvn_h) - 1) << t_sck_end_2_cnvn_h

        cnvn_pattern = []
        for _ in range(cnvn_state_duration):
            cnvn_pattern.append(cnvn & 0xFF)
            cnvn >>= 8
        assert cnvn == 0

        # CNVN polarity was swapped on PCB
        self.submodules.cnvn_phy = cnvn_phy = PatternSerializer(
            getattr(pins, "cnvn_n", None),
            getattr(pins, "cnvn_p", None),
            True,
            cnvn_pattern,
            0b0000_0000,  # IDLE low
        )

        sck = 0
        for _ in range(ADC_DATA_WIDTH):
            # 5 ns high, 5 ns low
            sck = sck << 10 | 0b11111_00000

        sck_state_duration = ceil((ADC_DATA_WIDTH * self.sck_period) / sys_clk_period)
        sck_pattern = []
        for _ in range(sck_state_duration):
            sck_pattern.append(sck & 0xFF)
            sck >>= 8
        assert sck == 0

        # SCK polarity was swapped on PCB
        self.submodules.sck_phy = sck_phy = PatternSerializer(
            getattr(pins, "sck_n", None),
            getattr(pins, "sck_p", None),
            True,
            sck_pattern,
            0b1111_1111,  # IDLE high
        )
        self.sample_period = len(cnvn_pattern) + len(sck_pattern) 

        self.submodules.fsm = fsm = FSM(reset_state="CNVN")
        update = Signal()
        fsm.act("CNVN",
            cnvn_phy.en.eq(1),
            If(cnvn_phy.done,
                # account for sck->clkout round trip and sdo sampling delay
                update.eq(1),
                NextState("SCK"),
            ),
        )

        fsm.act("SCK",
            sck_phy.en.eq(1),
            If(sck_phy.done, NextState("CNVN")),
        )

        # Using CLKOUT sample SDOs directly
        clkout = Signal()
        sdo_a, sdo_b, sdo_bn = Signal(), Signal(), Signal()
        self.comb += sdo_b.eq(~sdo_bn)
        if pins is not None:
            self.specials += [
                DifferentialInput(pins.clkout_p, pins.clkout_n, clkout),
                DifferentialInput(pins.sdo_p[0], pins.sdo_n[0], sdo_a),
                # SDOB polarity was swapped on PCB
                DifferentialInput(pins.sdo_n[1], pins.sdo_p[1], sdo_bn),
            ]

        self.clock_domains.cd_ret = ClockDomain("ret", reset_less=True)
        self.comb += self.cd_ret.clk.eq(clkout)

        # input ports are swapped (SMA_IN_0 = ADC_SDOB and SMA_IN_1 = ADC_SDOA)
        for i, sdo in enumerate([sdo_b, sdo_a]):
            sdo_sr = Signal(ADC_DATA_WIDTH)
            self.sync.ret += [
                sdo_sr[1:].eq(sdo_sr),
                sdo_sr[0].eq(sdo),
            ]
            self.sync += [
                If(update,
                    # ADC input polarity is swapped, flip the sign
                    self.sources[i].data.eq(~(sdo_sr) + 1),
                    self.sources[i].stb.eq(1),
                ).Else(
                    self.sources[i].stb.eq(0),
                ),
            ]


class PatternSerializer(Module):
    """
    A pattern serializer with a 8-bit TX serializer
    When en is HIGH, output the pattern sequentially. Otherwise output the idle word.

    :param pattern: a list of 8-bit words
    :param idle_word: a 8-bit word
    """

    def __init__(self, o_pad_p, o_pad_n, invert, pattern, idle_word):
        self.en = Signal()
        self.done = Signal()

        # # #

        len_pattern = len(pattern)
        assert len_pattern > 1

        if o_pad_p is None and o_pad_n is None:
            # For simulation
            tx = SimpleNamespace(din=Signal(8))
        else:
            # There is a one cycle delay loading the data into the serializer
            # SCK polarity was swapped on PCB
            self.submodules.tx = tx = TxSerializer(
                o_pad_p,
                o_pad_n,
                invert=invert,
                cd_4x="sys4x",
            )

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        for i, word in enumerate(pattern):
            if i == 0:
                fsm.act("IDLE",
                    If(self.en,
                        # output immediately to reduce delay
                        tx.din.eq(word & 0xFF),
                        NextState(str(1)),
                    ).Else(
                        tx.din.eq(idle_word & 0xFF),
                    ),
                )
            elif i != len_pattern - 1:
                fsm.act(str(i),
                    tx.din.eq(word & 0xFF),
                    NextState(str(i + 1)),
                )
            else:
                fsm.act(str(i),
                    tx.din.eq(word & 0xFF),
                    self.done.eq(1),
                    NextState("IDLE"),
                )
            word >>= 8
