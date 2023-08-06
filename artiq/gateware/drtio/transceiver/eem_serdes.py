from migen import *
from misoc.interconnect.csr import *
from misoc.cores.code_8b10b import SingleEncoder, Decoder
from artiq.gateware.drtio.core import TransceiverInterface, ChannelInterface


class RXSerdes(Module):
    def __init__(self, i_pads):
        self.rxdata = [ Signal(10) for _ in range(4) ]
        self.ld = [ Signal() for _ in range(4) ]
        self.cnt_in = [ Signal(5) for _ in range(4) ]
        self.cnt_out = [ Signal(5) for _ in range(4) ]
        self.bitslip = [ Signal() for _ in range(4) ]

        ser_in_no_dly = [ Signal() for _ in range(4) ]
        ser_in = [ Signal() for _ in range(4) ]
        shifts = [ Signal(2) for _ in range(4) ]

        for i in range(4):
            self.specials += [
                # Master deserializer
                Instance("ISERDESE2",
                    p_DATA_RATE="DDR",
                    p_DATA_WIDTH=10,
                    p_INTERFACE_TYPE="NETWORKING",
                    p_NUM_CE=1,
                    p_SERDES_MODE="MASTER",
                    p_IOBDELAY="IFD",
                    o_Q1=self.rxdata[i][9],
                    o_Q2=self.rxdata[i][8],
                    o_Q3=self.rxdata[i][7],
                    o_Q4=self.rxdata[i][6],
                    o_Q5=self.rxdata[i][5],
                    o_Q6=self.rxdata[i][4],
                    o_Q7=self.rxdata[i][3],
                    o_Q8=self.rxdata[i][2],
                    o_SHIFTOUT1=shifts[i][0],
                    o_SHIFTOUT2=shifts[i][1],
                    i_DDLY=ser_in[i],
                    i_BITSLIP=self.bitslip[i],
                    i_CLK=ClockSignal("sys5x"),
                    i_CLKB=~ClockSignal("sys5x"),
                    i_CE1=1,
                    i_RST=ResetSignal(),
                    i_CLKDIV=ClockSignal()),
                
                # Slave deserializer
                Instance("ISERDESE2",
                    p_DATA_RATE="DDR",
                    p_DATA_WIDTH=10,
                    p_INTERFACE_TYPE="NETWORKING",
                    p_NUM_CE=1,
                    p_SERDES_MODE="SLAVE",
                    p_IOBDELAY="IFD",
                    o_Q3=self.rxdata[i][1],
                    o_Q4=self.rxdata[i][0],
                    i_BITSLIP=self.bitslip[i],
                    i_CLK=ClockSignal("sys5x"),
                    i_CLKB=~ClockSignal("sys5x"),
                    i_CE1=1,
                    i_RST=ResetSignal(),
                    i_CLKDIV=ClockSignal(),
                    i_SHIFTIN1=shifts[i][0],
                    i_SHIFTIN2=shifts[i][1]),

                # Tunable delay
                # IDELAYCTRL is with the clocking
                Instance("IDELAYE2",
                    p_DELAY_SRC="IDATAIN",
                    p_SIGNAL_PATTERN="DATA",
                    p_CINVCTRL_SEL="FALSE",
                    p_HIGH_PERFORMANCE_MODE="TRUE",
                    # REFCLK refers to the clock source of IDELAYCTRL
                    p_REFCLK_FREQUENCY=200.0,
                    p_PIPE_SEL="FALSE",
                    p_IDELAY_TYPE="VAR_LOAD",
                    p_IDELAY_VALUE=0,

                    i_C=ClockSignal(),
                    i_LD=self.ld[i],
                    i_CE=0,
                    i_LDPIPEEN=0,
                    i_INC=1,            # Always increment

                    # Set the optimal delay tap via the aligner
                    i_CNTVALUEIN=self.cnt_in[i],
                    # Allow the aligner to check the tap value
                    o_CNTVALUEOUT=self.cnt_out[i],

                    i_IDATAIN=ser_in_no_dly[i],
                    o_DATAOUT=ser_in[i]
                ),

                # IOB
                Instance("IBUFDS",
                    p_DIFF_TERM="TRUE",
                    i_I=i_pads.p[i],
                    i_IB=i_pads.n[i],
                    o_O=ser_in_no_dly[i],
                )
            ]


class TXSerdes(Module):
    def __init__(self, o_pads):
        self.txdata = [ Signal(5) for _ in range(4) ]
        ser_out = [ Signal() for _ in range(4) ]
        t_out = [ Signal() for _ in range(4) ]

        for i in range(4):
            self.specials += [
                # Serializer
                Instance("OSERDESE2",
                    p_DATA_RATE_OQ="SDR", p_DATA_RATE_TQ="BUF",
                    p_DATA_WIDTH=5, p_TRISTATE_WIDTH=1,
                    p_INIT_OQ=0b00000,
                    o_OQ=ser_out[i],
                    o_TQ=t_out[i],
                    i_RST=ResetSignal(),
                    i_CLK=ClockSignal("sys5x"),
                    i_CLKDIV=ClockSignal(),
                    i_D1=self.txdata[i][0],
                    i_D2=self.txdata[i][1],
                    i_D3=self.txdata[i][2],
                    i_D4=self.txdata[i][3],
                    i_D5=self.txdata[i][4],
                    i_TCE=1, i_OCE=1,
                    i_T1=0
                ),

                # IOB
                Instance("OBUFTDS",
                    i_I=ser_out[i],
                    o_O=o_pads.p[i],
                    o_OB=o_pads.n[i],
                    # Always chain the 3-states input to serializer
                    # Vivado will complain otherwise
                    i_T=t_out[i],
                )
            ]


class MultiEncoder(Module):
    def __init__(self):
        # Keep the link layer interface identical to standard encoders
        self.d = [ Signal(8) for _ in range(2) ]
        self.k = [ Signal() for _ in range(2) ]

        # Output interface
        self.output = [ [ Signal(5) for _ in range(2) ] for _ in range(2) ]

        # Divided down clock
        # Alternate between sending encoded character to EEM 0/2 and EEM 1/3
        # every cycle
        self.clk_div2 = Signal()

        # Intermediate registers for output and disparity
        # More significant bits are buffered due to channel geometry
        # Disparity bit is delayed. The same encoder is shared by 2 SERDES
        output_bufs = [Signal(5) for _ in range(2)]
        disp_bufs = [Signal() for _ in range(2)]

        encoders = [SingleEncoder() for _ in range(2)]
        self.submodules += encoders

        # Encoded characters are routed to the EEM pairs:
        # The first character goes through EEM 0/2
        # The second character goes through EEM 1/3, and repeat...
        # Lower order bits go first, so higher order bits are buffered and
        # transmitted in the next cycle.
        for d, k, output, output_buf, disp_buf, encoder in \
                zip(self.d, self.k, self.output, output_bufs, disp_bufs, encoders):
            self.comb += [
                encoder.d.eq(d),
                encoder.k.eq(k),

                If(self.clk_div2,
                    output[0].eq(encoder.output[0:5]),
                    output[1].eq(output_buf),
                ).Else(
                    output[0].eq(output_buf),
                    output[1].eq(encoder.output[0:5]),
                ),
            ]
            # Handle intermediate registers
            self.sync += [
                disp_buf.eq(encoder.disp_out),
                encoder.disp_in.eq(disp_buf),
                output_buf.eq(encoder.output[5:10]),
            ]


# Unlike the usual 8b10b decoder, it needs to know which SERDES to decode
class CrossbarDecoder(Module):
    def __init__(self):
        self.raw_input = [ Signal(5) for _ in range(2) ]
        self.d = Signal(8)
        self.k = Signal()

        # Divided down clock
        # Alternate between decoding encoded character from EEM 0/2 and
        # EEM 1/3 every cycle
        self.clk_div2 = Signal()

        # Extended bitslip mechanism. ISERDESE2 bitslip can only adjust bit
        # position by 5 bits (1 cycle). However, an encoded character takes 2
        # cycles to transmit/receive. Asserting wordslip effectively injects
        # an additional 5 bit position worth of bitslips.
        self.wordslip = Signal()

        # Intermediate register for input
        buffer = Signal(5)

        self.submodules.decoder = Decoder()

        # The decoder does the following actions:
        # - Process received characters from EEM 0/2
        # - Same, but from EEM 1/3
        #
        # Wordslipping is equivalent to swapping task between clock cycles.
        # (i.e. Swap processing target. Instead of processing EEM 0/2, process
        # EEM 1/3, and vice versa on the next cycle.) This effectively shifts
        # the processing time of any encoded character by 1 clock cycle (5
        # bitslip equivalent without considering oversampling, 10 otherwise).
        self.sync += [
            If(self.clk_div2 ^ self.wordslip,
                buffer.eq(self.raw_input[1])
            ).Else(
                buffer.eq(self.raw_input[0])
            )
        ]

        self.comb += [
            If(self.clk_div2 ^ self.wordslip,
                self.decoder.input.eq(Cat(buffer, self.raw_input[0]))
            ).Else(
                self.decoder.input.eq(Cat(buffer, self.raw_input[1]))
            )
        ]

        self.comb += [
            self.d.eq(self.decoder.d),
            self.k.eq(self.decoder.k),
        ]


class BangBangPhaseDetector(Module):
    def __init__(self):
        self.s = Signal(3)

        self.high = Signal()
        self.low = Signal()

        self.comb += If(~self.s[0] & self.s[2],
            self.high.eq(self.s[1]),
            self.low.eq(~self.s[1]),
        ).Else(
            self.high.eq(0),
            self.low.eq(0),
        )


class RisingEdgeCounter(Module, AutoCSR):
    def __init__(self):
        self.high_count = CSRStatus(18)
        self.low_count = CSRStatus(18)

        # Odd indices are always oversampled bits
        self.rxdata = Signal(10)

        # Detect rising edges & measure
        self.submodules.detector = BangBangPhaseDetector()
        self.comb += self.detector.s.eq(self.rxdata[:3])

        self.reset = CSR()
        self.enable = CSRStorage()

        self.overflow = CSRStatus()
        high_carry = Signal()
        low_carry = Signal()

        self.sync += [
            If(self.reset.re,
                self.high_count.status.eq(0),
                self.low_count.status.eq(0),
                high_carry.eq(0),
                low_carry.eq(0),
                self.overflow.status.eq(0),
            ).Elif(self.enable.storage,
                Cat(self.high_count.status, high_carry).eq(
                    self.high_count.status + self.detector.high),
                Cat(self.low_count.status, low_carry).eq(
                    self.low_count.status + self.detector.low),
                If(high_carry | low_carry, self.overflow.status.eq(1)),
            )
        ]


class CommaReader(Module, AutoCSR):
    def __init__(self):
        self.decoder_comma = Signal()
        self.reset = CSR()
        self.comma = CSRStatus()

        self.sync += If(self.reset.re,
            self.comma.status.eq(0),
        ).Else(
            self.comma.status.eq(self.comma.status | self.decoder_comma),
        )


class SerdesSingle(Module, AutoCSR):
    def __init__(self, i_pads, o_pads, debug=False):
        # Serdes Module
        self.submodules.rx_serdes = RXSerdes(i_pads)
        self.submodules.tx_serdes = TXSerdes(o_pads)

        # EEM lane select
        self.eem_sel = CSRStorage(2)

        # CSR for bitslip
        self.bitslip = CSR()

        for i in range(4):
            self.comb += self.rx_serdes.bitslip[i].eq(self.bitslip.re)
        
        self.dly_cnt_in = CSRStorage(5)
        self.dly_ld = CSR()

        for i in range(4):
            self.comb += [
                self.rx_serdes.cnt_in[i].eq(self.dly_cnt_in.storage),
                self.rx_serdes.ld[i].eq((self.eem_sel.storage == i) & self.dly_ld.re),
            ]
        
        self.dly_cnt_out = CSRStatus(5)

        self.comb += Case(self.eem_sel.storage, {
            idx: self.dly_cnt_out.status.eq(self.rx_serdes.cnt_out[idx]) for idx in range(4)
        })
        
        # CSR for global decoding phase
        # This is to determine if this cycle should decode SERDES 0 or 1
        self.wordslip = CSRStorage()

        # Encoder/Decoder interfaces
        self.submodules.encoder = MultiEncoder()
        self.submodules.decoders = decoders = Array(CrossbarDecoder() for _ in range(2))

        # Control decoders phase
        self.comb += [
            decoders[0].wordslip.eq(self.wordslip.storage),
            decoders[1].wordslip.eq(self.wordslip.storage),
        ]
        
        # Route encoded symbols to TXSerdes, decoded symbols from RXSerdes
        for i in range(4):
            self.comb += [
                self.tx_serdes.txdata[i].eq(self.encoder.output[i//2][i%2]),
                decoders[i//2].raw_input[i%2].eq(self.rx_serdes.rxdata[i][0::2]),
            ]

        self.clk_div2 = Signal()
        self.comb += [
            self.encoder.clk_div2.eq(self.clk_div2),
            self.decoders[0].clk_div2.eq(self.clk_div2),
            self.decoders[1].clk_div2.eq(self.clk_div2),
        ]

        # Monitor lane 0 decoder output for bitslip alignment
        self.submodules.reader = CommaReader()
        self.comb += self.reader.decoder_comma.eq(
            ((decoders[0].d == 0x3C) | (decoders[0].d == 0xBC)) & decoders[0].k)

        # Read rxdata for rising edge alignment
        self.submodules.counter = RisingEdgeCounter()

        self.comb += Case(self.eem_sel.storage, {
            lane_idx: self.counter.rxdata.eq(self.rx_serdes.rxdata[lane_idx]) for lane_idx in range(4)
        })


class EEMSerdes(Module, TransceiverInterface):
    def __init__(self, platform, data_pads):
        self.rx_ready = CSRStorage()

        clk_div2 = Signal()
        self.sync += clk_div2.eq(~clk_div2)

        self.submodules.serdes = SerdesSingle(*data_pads[0])
        self.comb += self.serdes.clk_div2.eq(clk_div2)

        chan_if = ChannelInterface(self.serdes.encoder, self.serdes.decoders)
        self.comb += chan_if.rx_ready.eq(self.rx_ready.storage)
        channel_interfaces = [chan_if]

        TransceiverInterface.__init__(self, channel_interfaces)

        self.comb += [
            getattr(self, "cd_rtio_rx0").clk.eq(ClockSignal()),
            getattr(self, "cd_rtio_rx0").rst.eq(ResetSignal())
        ]
