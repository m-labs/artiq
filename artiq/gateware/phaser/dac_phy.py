from migen import *

from operator import xor

DAC_DATA_WIDTH = 16
DAC_FIFO_DEPTH = 8


class DAC34H84PHY(Module):
    """
    A DAC34H84 PHY designed for 125 MHz sys clock

    Supports:
    - A 500(n=4)/250(n=2) MHz data clock output
    - Two 1000(n=4)/500(n=2) MSPS time interleaved data outputs
    - An even parity bit output
    - FIFO pointer and PLL N-divider synchronization
    """

    def __init__(self, data_pins, ctrl_pins, n):

        assert n in [2, 4]

        self.alarm = Signal()
        self.en = Signal()
        self.reset_n = Signal()
        self.sleep = Signal()

        self.sinks_a = [Signal(DAC_DATA_WIDTH) for _ in range(n)]
        self.sinks_b = [Signal(DAC_DATA_WIDTH) for _ in range(n)]
        self.sinks_c = [Signal(DAC_DATA_WIDTH) for _ in range(n)]
        self.sinks_d = [Signal(DAC_DATA_WIDTH) for _ in range(n)]

        # # #

        # Control / status pins
        self.comb += [
            self.alarm.eq(ctrl_pins.alarm),
            ctrl_pins.txena.eq(self.en),
            ctrl_pins.resetb.eq(self.reset_n),
            ctrl_pins.sleep.eq(self.sleep),
        ]

        # Data clock generation
        self.submodules.dataclk_phy = DataClockPHY(data_pins, n)

        # Time interleaved data and even parity bit
        self.submodules.data_phy = data_phy = DataPHY(data_pins, n)
        self.submodules.even_parity_phy = even_parity_phy = EvenParityPHY(data_pins, n)
        for i in range(n):
            self.sync += [
                data_phy.sinks_a[i].eq(self.sinks_a[i]),
                data_phy.sinks_b[i].eq(self.sinks_b[i]),
                data_phy.sinks_c[i].eq(self.sinks_c[i]),
                data_phy.sinks_d[i].eq(self.sinks_d[i]),
                even_parity_phy.sinks_a[i].eq(self.sinks_a[i]),
                even_parity_phy.sinks_b[i].eq(self.sinks_b[i]),
                even_parity_phy.sinks_c[i].eq(self.sinks_c[i]),
                even_parity_phy.sinks_d[i].eq(self.sinks_d[i]),
            ]

        # FIFO pointers and PLL N divider synchronization
        # ISTR:
        # - sync the FIFO pointers
        # - as a frame indicator for data pattern testing
        # SYNC:
        # - DAC PLL is synchronized by the rising edge of LVDS SYNC signal going to the N-divider circuit - SLAA584 Section 2.4
        # - The divided clock is also used as the OSTR signal to synchronize the FIFO write pointer
        self.submodules.istr_sync_phy = IstrSyncPHY(data_pins, n)


class IstrSyncPHY(Module):
    def __init__(self, pins, n):
        self.submodules.istr_phy = istr_phy = TxInterleavedSerializer(
            pins.istr_parityab_p, pins.istr_parityab_n, n
        )

        self.submodules.sync_phy = sync_phy = TxInterleavedSerializer(
            pins.sync_p, pins.sync_n, n
        )

        # SLAS751D Section 7.3.4
        # - rising edge on the sync signal source (ISTR or SYNC) causes the pointer to return to its original position
        # - it is necessary to have the ISTR and SYNC signals to repeat at multiples of 8 FIFO samples (i.e. mutiple of FIFO size)
        # So we just raise the signals when the FIFO is full.

        fifo_full_interval = DAC_FIFO_DEPTH // n
        write_read_counter = Signal(max=fifo_full_interval)
        self.sync += [
            If(
                write_read_counter == fifo_full_interval - 1,
                write_read_counter.eq(write_read_counter.reset),
            ).Else(write_read_counter.eq(write_read_counter + 1))
        ]
        self.comb += [
            istr_phy.din_0[0].eq(write_read_counter == 0),
            sync_phy.din_0[0].eq(write_read_counter == 0),
        ]


class DataClockPHY(Module):
    """
    A data clock generator using a 8-bit TX serializer
    """
    def __init__(self, pins, n):
        # Using a 90 degree clock offset to sample all the data and control signals to avoid metastability
        if n == 4:
            # delay 0.5 UI (0.5 ns)
            data_clk_phy = TxSerializer(
                pins.data_clk_p,
                pins.data_clk_n,
                invert=False,
                cd_4x="sys4x_dqs",
            )
            self.comb += data_clk_phy.din.eq(0b0101_0101)
        elif n == 2:
            # delay 0.5 UI (1 ns)
            data_clk_phy = TxSerializer(
                pins.data_clk_p,
                pins.data_clk_n,
                invert=False,
                cd_4x="sys4x",
            )
            self.comb += data_clk_phy.din.eq(0b0110_0110)
        self.submodules += data_clk_phy


class EvenParityPHY(Module):
    def __init__(self, pins, n):
        self.sinks_a = [Signal(DAC_DATA_WIDTH) for _ in range(n)]
        self.sinks_b = [Signal(DAC_DATA_WIDTH) for _ in range(n)]
        self.sinks_c = [Signal(DAC_DATA_WIDTH) for _ in range(n)]
        self.sinks_d = [Signal(DAC_DATA_WIDTH) for _ in range(n)]

        # # #

        parity_ac = Signal(n)
        parity_bd = Signal(n)

        for i in range(n):
            sample_a = self.sinks_a[i]
            sample_b = self.sinks_b[i]
            sample_c = self.sinks_c[i]
            sample_d = self.sinks_d[i]
            self.comb += [
                parity_ac[i].eq(
                    reduce(
                        xor, [sample_a[j] ^ sample_c[j] for j in range(DAC_DATA_WIDTH)]
                    )
                ),
                parity_bd[i].eq(
                    reduce(
                        xor, [sample_b[j] ^ sample_d[j] for j in range(DAC_DATA_WIDTH)]
                    )
                ),
            ]

        self.submodules.tx = tx = TxInterleavedSerializer(
            pins.paritycd_p, pins.paritycd_n, n
        )
        self.comb += [
            tx.din_0.eq(parity_ac),
            tx.din_1.eq(parity_bd),
        ]


class DataPHY(Module):
    def __init__(self, pins, n):
        assert DAC_DATA_WIDTH == len(pins.data_a_p) == len(pins.data_b_p)
        self.sinks_a = [Signal(DAC_DATA_WIDTH) for _ in range(n)]
        self.sinks_b = [Signal(DAC_DATA_WIDTH) for _ in range(n)]
        self.sinks_c = [Signal(DAC_DATA_WIDTH) for _ in range(n)]
        self.sinks_d = [Signal(DAC_DATA_WIDTH) for _ in range(n)]

        # # #

        def get_tx_bits(sinks, nbit):
            return Cat(s[nbit] for s in sinks)

        # A3, B8: p-n swapped on pcb
        inverted_pad = [(0, 3), (1, 8)]
        txpins_arg = []
        for port_i, port in enumerate(
            [(pins.data_a_p, pins.data_a_n), (pins.data_b_p, pins.data_b_n)]
        ):
            for pad_i, (pad_p, pad_n) in enumerate(zip(*port)):
                if port_i == 0:
                    sink_0, sink_1 = self.sinks_a, self.sinks_b
                else:
                    sink_0, sink_1 = self.sinks_c, self.sinks_d

                inverted = (port_i, pad_i) in inverted_pad
                pad_p, pad_n = (pad_n, pad_p) if inverted else (pad_p, pad_n)

                txpins_arg.append(
                    [
                        get_tx_bits(sink_0, pad_i),
                        get_tx_bits(sink_1, pad_i),
                        pad_p,
                        pad_n,
                        inverted,
                    ]
                )

        for sink_0_bits, sink_1_bits, pad_p, pad_n, inverted in txpins_arg:
            # From SLAS751D section 7.3.3
            # The data for channels A and B or (C and D) is interleaved in the form
            # A0[i], B0[i], A1[i], B1[i], A2[i]… into the DAB[i]P/N LVDS inputs.
            tx = TxInterleavedSerializer(pad_p, pad_n, n, inverted)

            self.submodules += tx
            self.comb += [
                tx.din_0.eq(sink_0_bits),
                tx.din_1.eq(sink_1_bits),
            ]


class TxSerializer(Module):
    """
    A 8-bit DDR TX serializer
    """

    def __init__(self, o_pad_p, o_pad_n, invert, cd_4x):
        self.din = Signal(8)

        # # #

        ser_out = Signal()
        t_out = Signal()
        self.specials += [
            # Serializer
            Instance(
                "OSERDESE2",
                p_DATA_RATE_OQ="DDR",
                p_DATA_RATE_TQ="BUF",
                p_DATA_WIDTH=8,
                p_TRISTATE_WIDTH=1,
                p_INIT_OQ=0x00,
                o_OQ=ser_out,
                o_TQ=t_out,
                i_RST=ResetSignal(),
                i_CLK=ClockSignal(cd_4x),
                i_CLKDIV=ClockSignal(),
                i_D1=self.din[0] ^ invert,
                i_D2=self.din[1] ^ invert,
                i_D3=self.din[2] ^ invert,
                i_D4=self.din[3] ^ invert,
                i_D5=self.din[4] ^ invert,
                i_D6=self.din[5] ^ invert,
                i_D7=self.din[6] ^ invert,
                i_D8=self.din[7] ^ invert,
                i_TCE=1,
                i_OCE=1,
                i_T1=0,
            ),
            # IOB
            Instance(
                "OBUFTDS",
                i_I=ser_out,
                i_T=t_out,
                o_O=o_pad_p,
                o_OB=o_pad_n,
            ),
        ]


class TxInterleavedSerializer(Module):
    """
    A time interleaved serializer with a 8-bit TX serializer
    Each cycle, it sends the interleaved data as follows
    n = 4: din_0[0], din_1[0], din_0[1], din_1[1], din_0[2], din_1[2], din_0[3], din_1[3]
    n = 2: din_0[0], din_0[0], din_1[0], din_1[0], din_0[1], din_0[1], din_1[1], din_1[1]
    ...
    """

    def __init__(self, o_pad_p, o_pad_n, n, invert=False, cd_4x="sys4x"):
        self.submodules.serializer = serializer = TxSerializer(
            o_pad_p, o_pad_n, invert, cd_4x
        )
        self.din_0 = Signal(n)
        self.din_1 = Signal(n)

        assert len(serializer.din) % len(Cat(self.din_0, self.din_1)) == 0
        # try to fit interleaved din_0, din_1 into out by repeating each element if necessary
        repeats = len(serializer.din) // len(Cat(self.din_0, self.din_1))

        interleaved = []
        for first, second in zip(self.din_0, self.din_1):
            interleaved.extend([first for _ in range(repeats)])
            interleaved.extend([second for _ in range(repeats)])
        self.comb += serializer.din.eq(Cat(*interleaved))
