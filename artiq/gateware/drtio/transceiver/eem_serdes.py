from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
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
        self.o = [ Signal() for _ in range(4) ]

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
                    o_O=self.o[i],
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

        self.ext_rst = Signal()

        for i in range(4):
            self.specials += [
                # Serializer
                Instance("OSERDESE2",
                    p_DATA_RATE_OQ="SDR", p_DATA_RATE_TQ="BUF",
                    p_DATA_WIDTH=5, p_TRISTATE_WIDTH=1,
                    p_INIT_OQ=0b00000,
                    o_OQ=ser_out[i],
                    o_TQ=t_out[i],
                    i_RST=ResetSignal() | self.ext_rst,
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
                    i_T=t_out[i],
                )
            ]


# This module owns 2 8b10b encoders, each encoder route codewords to 2 lanes,
# through time multiplexing. The scheduler releases 2 bytes every clock cycle,
# and the encoders each encode 1 byte.
#
# Since each lane only transmits 5 bits per sysclk cycle, the encoder selects
# a lane to first transmit the least significant word (LSW, 5 bits), and send
# the rest in the next cycle using the same lane. It takes advantage of the
# arrival sequence of bytes from the scrambler to achieve the transmission
# pattern shown in the MultiDecoder module.
class MultiEncoder(Module):
    def __init__(self):
        # Keep the link layer interface identical to standard encoders
        self.d = [ Signal(8) for _ in range(2) ]
        self.k = [ Signal() for _ in range(2) ]

        # Output interface
        self.output = [ [ Signal(5) for _ in range(2) ] for _ in range(2) ]

        # Clock enable signal
        # Alternate between sending encoded character to EEM 0/2 and EEM 1/3
        # every cycle
        self.clk_div2 = Signal()

        # Intermediate registers for output and disparity
        # More significant bits are buffered due to channel geometry
        # Disparity bit is delayed. The same encoder is shared by 2 SERDES
        output_bufs = [ Signal(5) for _ in range(2) ]
        disp_bufs = [ Signal() for _ in range(2) ]

        encoders = [ SingleEncoder() for _ in range(2) ]
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


# Owns 2 8b10b decoders, each decodes data from lane 0/1 and lane 2/3class
# respectively. The decoders are time multiplexed among the 2 lanes, and
# each decoder decodes exactly 1 lane per sysclk cycle.
#
# The transmitter could send the following data pattern over the 4 lanes.
# Capital letters denote the most significant word (MSW); The lowercase denote
# the least significant word (LSW) of the same 8b10b character.
#
# Cycle \ Lane  0   1   2   3
#       0       a   Y   b   Z
#       1       A   c   B   d
#       2       a'  C   b'  D
#       3       A'  c'  B'  d'
#
# Lane 0/2 and lane 1/3 transmit word of different significance by design (see
# MultiEncoder).
#
# This module buffers the LSW, and immediately send the whole 8b10b character
# to the coresponding decoder once the MSW is also received.
class MultiDecoder(Module):
    def __init__(self):
        self.raw_input = [ Signal(5) for _ in range(2) ]
        self.d = Signal(8)
        self.k = Signal()

        # Clock enable signal
        # Alternate between decoding encoded character from EEM 0/2 and
        # EEM 1/3 every cycle
        self.clk_div2 = Signal()

        # Extended bitslip mechanism. ISERDESE2 bitslip can only adjust bit
        # position by 5 bits (1 cycle). However, an encoded character takes 2
        # cycles to transmit/receive. The module needs to correctly reassemble
        # the 8b10b character. This is useful received waveform is the 1-cycle
        # delayed version of the above waveform. The same scheme would
        # incorrectly buffer words and create wrong symbols.
        #
        # Hence, wordslip put LSW as MSW and vice versa, effectively injects
        # an additional 5 bit positions worth of bitslips.
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


class PhaseErrorCounter(Module, AutoCSR):
    def __init__(self):
        self.high_count = CSRStatus(18)
        self.low_count = CSRStatus(18)

        # Odd indices are always oversampled bits
        self.rxdata = Signal(10)

        # Measure setup/hold timing, count phase error in the following
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


class SerdesSingle(Module):
    def __init__(self, i_pads, o_pads):
        # Serdes modules
        self.submodules.rx_serdes = RXSerdes(i_pads)
        self.submodules.tx_serdes = TXSerdes(o_pads)

        self.lane_sel = Signal(2)

        self.bitslip = Signal()

        for i in range(4):
            self.comb += self.rx_serdes.bitslip[i].eq(self.bitslip)
        
        self.dly_cnt_in = Signal(5)
        self.dly_ld = Signal()

        for i in range(4):
            self.comb += [
                self.rx_serdes.cnt_in[i].eq(self.dly_cnt_in),
                self.rx_serdes.ld[i].eq((self.lane_sel == i) & self.dly_ld),
            ]
        
        self.dly_cnt_out = Signal(5)

        self.comb += Case(self.lane_sel, {
            idx: self.dly_cnt_out.eq(self.rx_serdes.cnt_out[idx]) for idx in range(4)
        })
        
        self.wordslip = Signal()

        # Encoder/Decoder interfaces
        self.submodules.encoder = MultiEncoder()
        self.submodules.decoders = decoders = Array(MultiDecoder() for _ in range(2))

        self.comb += [
            decoders[0].wordslip.eq(self.wordslip),
            decoders[1].wordslip.eq(self.wordslip),
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
        self.comma_align_reset = Signal()
        self.comma = Signal()

        self.sync += If(self.comma_align_reset,
            self.comma.eq(0),
        ).Elif(~self.comma,
            self.comma.eq(
                ((decoders[0].d == 0x3C) | (decoders[0].d == 0xBC))
                & decoders[0].k))


class OOBReset(Module):
    def __init__(self, platform, iserdes_o):
        self.clock_domains.cd_clk100 = ClockDomain()
        self.specials += [
            Instance("BUFR",
                i_I=ClockSignal("clk200"),
                o_O=ClockSignal("clk100"),
                p_BUFR_DIVIDE="2"),
            AsyncResetSynchronizer(self.cd_clk100, ResetSignal("clk200")),
        ]

        idle_low = Signal()
        idle_high = Signal()

        self.rst = Signal(reset=1)

        # Detect the lack of transitions (idle) within a clk100 cycle
        for idle, source in [
                (idle_low, iserdes_o), (idle_high, ~iserdes_o)]:
            idle_meta = Signal()
            ff_pair = [ff1, ff2] = [
                Instance("FDCE", p_INIT=1, i_D=1, i_CLR=source,
                    i_CE=1, i_C=ClockSignal("clk100"), o_Q=idle_meta,
                    attr={"async_reg"}),
                Instance("FDCE", p_INIT=1, i_D=idle_meta, i_CLR=0,
                    i_CE=1, i_C=ClockSignal("clk100"), o_Q=idle,
                    attr={"async_reg"}),
            ]
            self.specials += ff_pair

            platform.add_platform_command(
                "set_false_path -quiet -to {ff1}/CLR", ff1=ff1)
            # Capture transition detected by FF1/Q in FF2/D
            platform.add_platform_command(
                "set_max_delay 2 -quiet "
                "-from {ff1}/Q -to {ff2}/D", ff1=ff1, ff2=ff2)

        # Detect activity for the last 2**15 clk100 cycles
        self.submodules.fsm = fsm = ClockDomainsRenamer("clk100")(
            FSM(reset_state="WAIT_TRANSITION"))
        counter = Signal(15, reset=0x7FFF)

        # Keep sysclk reset asserted until transition is detected for a
        # continuous 2**15 clk100 cycles
        fsm.act("WAIT_TRANSITION",
            self.rst.eq(1),
            If(idle_low | idle_high,
                NextValue(counter, 0x7FFF),
            ).Else(
                If(counter == 0,
                    NextState("WAIT_NO_TRANSITION"),
                    NextValue(counter, 0x7FFF),
                ).Else(
                    NextValue(counter, counter - 1),
                )
            )
        )

        # Reassert sysclk reset if there are no transition for the last 2**15
        # clk100 cycles.
        fsm.act("WAIT_NO_TRANSITION",
            self.rst.eq(0),
            If(idle_low | idle_high,
                If(counter == 0,
                    NextState("WAIT_TRANSITION"),
                    NextValue(counter, 0x7FFF),
                ).Else(
                    NextValue(counter, counter - 1),
                )
            ).Else(
                NextValue(counter, 0x7FFF),
            )
        )


class EEMSerdes(Module, TransceiverInterface, AutoCSR):
    def __init__(self, platform, data_pads):
        self.rx_ready = CSRStorage()

        self.transceiver_sel = CSRStorage(max(1, log2_int(len(data_pads))))
        self.lane_sel = CSRStorage(2)

        self.bitslip = CSR()

        self.dly_cnt_in = CSRStorage(5)
        self.dly_ld = CSR()
        self.dly_cnt_out = CSRStatus(5)

        # Slide a word back/forward by 1 cycle, shared by all lanes of the
        # same transceiver. This is to determine if this cycle should decode
        # lane 0/2 or lane 1/3. See MultiEncoder/MultiDecoder for the full
        # scheme & timing.
        self.wordslip = CSRStorage()

        # Monitor lane 0 decoder output for bitslip alignment
        self.comma_align_reset = CSR()
        self.comma = CSRStatus()

        clk_div2 = Signal()
        self.sync += clk_div2.eq(~clk_div2)

        channel_interfaces = []
        serdes_list = []
        for i_pads, o_pads in data_pads:
            serdes = SerdesSingle(i_pads, o_pads)
            self.comb += serdes.clk_div2.eq(clk_div2)
            serdes_list.append(serdes)

            chan_if = ChannelInterface(serdes.encoder, serdes.decoders)
            self.comb += chan_if.rx_ready.eq(self.rx_ready.storage)
            channel_interfaces.append(chan_if)

        # Route CSR signals using transceiver_sel
        self.comb += Case(self.transceiver_sel.storage, {
            trx_no: [
                serdes.bitslip.eq(self.bitslip.re),
                serdes.dly_ld.eq(self.dly_ld.re),

                self.dly_cnt_out.status.eq(serdes.dly_cnt_out),
                self.comma.status.eq(serdes.comma),
            ] for trx_no, serdes in enumerate(serdes_list)
        })

        # Wordslip needs to be latched. It needs to hold when calibrating
        # other transceivers and/or after calibration.
        self.sync += If(self.wordslip.re,
            Case(self.transceiver_sel.storage, {
                trx_no: [
                    serdes.wordslip.eq(self.wordslip.storage)
                ] for trx_no, serdes in enumerate(serdes_list)
            })
        )

        for serdes in serdes_list:
            self.comb += [
                # Delay counter write only comes into effect after dly_ld
                # So, just MUX dly_ld instead.
                serdes.dly_cnt_in.eq(self.dly_cnt_in.storage),

                # Comma align reset & lane selection can be broadcasted
                # without MUXing. Transceivers are aligned one-by-one
                serdes.lane_sel.eq(self.lane_sel.storage),
                serdes.comma_align_reset.eq(self.comma_align_reset.re),
            ]
        
        # Setup/hold timing calibration module
        self.submodules.counter = PhaseErrorCounter()
        self.comb += Case(self.transceiver_sel.storage, {
            trx_no: Case(self.lane_sel.storage, {
                lane_idx: self.counter.rxdata.eq(serdes.rx_serdes.rxdata[lane_idx]) 
                    for lane_idx in range(4)
            }) for trx_no, serdes in enumerate(serdes_list)
        })

        self.submodules += serdes_list

        self.submodules.oob_reset = OOBReset(platform, serdes_list[0].rx_serdes.o[0])
        self.rst = self.oob_reset.rst
        self.rst.attr.add("no_retiming")

        TransceiverInterface.__init__(self, channel_interfaces, async_rx=False)

        for tx_en, serdes in zip(self.txenable.storage, serdes_list):
            self.comb += serdes.tx_serdes.ext_rst.eq(~tx_en)
