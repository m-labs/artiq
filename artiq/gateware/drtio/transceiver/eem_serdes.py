from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.io import DifferentialInput, DifferentialOutput
from migen.genlib.fifo import AsyncFIFO
from misoc.cores import gpio
from misoc.interconnect.csr import *
from misoc.cores.code_8b10b import SingleEncoder, Decoder
from artiq.gateware.drtio.core import TransceiverInterface, ChannelInterface


class RXPhy(Module):
    def __init__(self, i_pads):
        self.o = [Signal() for _ in range(4)]

        for i in range(4):
            self.specials += Instance("IBUFDS",
                i_I=i_pads[i].p,
                i_IB=i_pads[i].n,
                o_O=self.o[i],
            )


class TXPhy(Module):
    def __init__(self, o_pads):
        self.i = [Signal() for _ in range(4)]
        self.t = [Signal() for _ in range(4)]

        for i in range(4):
            self.specials += Instance("OBUFTDS",
                i_I=self.i[i],
                o_O=o_pads[i].p,
                o_OB=o_pads[i].n,
                # Always chain the 3-states input to serializer
                # Vivado will complain otherwise
                i_T=self.t[i],
            )


class RXSerdes(Module):
    def __init__(self):
        self.rxdata = [ Signal(10) for _ in range(4) ]
        self.ser_in_no_dly = [ Signal() for _ in range(4) ]
        self.ld = [ Signal() for _ in range(4) ]
        self.cnt_in = [ Signal(5) for _ in range(4) ]
        self.cnt_out = [ Signal(5) for _ in range(4) ]
        self.bitslip = [ Signal() for _ in range(4) ]

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
                    i_CLK=ClockSignal("eem_sys5x"),
                    i_CLKB=~ClockSignal("eem_sys5x"),
                    i_CE1=1,
                    i_RST=ResetSignal("eem_sys"),
                    i_CLKDIV=ClockSignal("eem_sys")),
                
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
                    i_CLK=ClockSignal("eem_sys5x"),
                    i_CLKB=~ClockSignal("eem_sys5x"),
                    i_CE1=1,
                    i_RST=ResetSignal("eem_sys"),
                    i_CLKDIV=ClockSignal("eem_sys"),
                    i_SHIFTIN1=shifts[i][0],
                    i_SHIFTIN2=shifts[i][1]),

                # Tunable delay
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

                    i_IDATAIN=self.ser_in_no_dly[i],
                    o_DATAOUT=ser_in[i]
                ),

                # IDELAYCTRL is with the clocking
            ]


class TXSerdes(Module):
    def __init__(self):
        self.txdata = [ Signal(5) for _ in range(4) ]
        self.ser_out = [ Signal() for _ in range(4) ]
        self.t_out = [ Signal() for _ in range(4) ]

        # TX SERDES
        for i in range(4):
            self.specials += Instance("OSERDESE2",
                p_DATA_RATE_OQ="SDR", p_DATA_RATE_TQ="BUF",
                p_DATA_WIDTH=5, p_TRISTATE_WIDTH=1,
                p_INIT_OQ=0b00000,
                o_OQ=self.ser_out[i],
                o_TQ=self.t_out[i],
                i_RST=ResetSignal("eem_sys"),
                i_CLK=ClockSignal("eem_sys5x"),
                i_CLKDIV=ClockSignal("eem_sys"),
                i_D1=self.txdata[i][0],
                i_D2=self.txdata[i][1],
                i_D3=self.txdata[i][2],
                i_D4=self.txdata[i][3],
                i_D5=self.txdata[i][4],
                i_TCE=1, i_OCE=1,
                i_T1=0)


class MultiEncoder(Module):
    def __init__(self):
        WORDS = 2
        # Keep the link layer interface identical to standard encoders
        self.d = [Signal(8) for _ in range(WORDS)]
        self.k = [Signal() for _ in range(WORDS)]

        # Alignment control: Keep sending K.28.5
        self.align = Signal()

        # Output interface is simplified because we have custom physical layer
        self.output = [Signal(10) for _ in range(WORDS)]

        # Phase of the encoder
        # Alternate crossbar between encoder and SERDES every cycle
        self.phase = Signal()

        # Intermediate registers for output and disparity
        # More significant bits are buffered due to channel geometry
        # Disparity bit is delayed. The same encoder is shared by 2 SERDES
        output_bufs = [Signal(5) for _ in range(WORDS)]
        disp_bufs = [Signal() for _ in range(WORDS)]

        encoders = [SingleEncoder() for _ in range(WORDS)]
        self.submodules += encoders

        for d, k, output, output_buf, disp_buf, encoder in \
                zip(self.d, self.k, self.output, output_bufs, disp_bufs, encoders):
            self.comb += [
                If(self.align,
                    encoder.d.eq(0xBC),
                    encoder.k.eq(1),
                ).Else(
                    encoder.d.eq(d),
                    encoder.k.eq(k),
                ),

                # Implementing switching crossbar
                If(self.phase,
                    output.eq(Cat(encoder.output[0:5], output_buf))
                ).Else(
                    output.eq(Cat(output_buf, encoder.output[0:5]))
                ),
            ]
            # Handle intermediate registers
            self.sync.eem_sys += [
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

        # Notifier signal when group alignmnet is completed
        self.delay = Signal(2)
        self.phase = Signal()

        # Optional extra stage for both lanes
        self.delay_buf = [ Signal(5) for _ in range(2) ]
        self.sync.eem_sys += [
            self.delay_buf[idx].eq(self.raw_input[idx]) for idx in range(2)
        ]

        # Intermediate register for input
        buffer = Signal(5)

        self.submodules.decoder = Decoder()

        # Update phase & synchronous elements
        self.sync.eem_sys += [
            If(~self.phase,
                If(~self.delay[0],
                    buffer.eq(self.raw_input[0]),
                ).Else(
                    buffer.eq(self.delay_buf[0]),
                )
            ).Else(
                If(~self.delay[1],
                    buffer.eq(self.raw_input[1]),
                ).Else(
                    buffer.eq(self.delay_buf[1]),
                )
            )
        ]
        
        # Send appropriate input to decoder
        self.comb += [
            If(self.phase,
                If(~self.delay[0],
                    self.decoder.input.eq(Cat(buffer, self.raw_input[0])),
                ).Else(
                    self.decoder.input.eq(Cat(buffer, self.delay_buf[0])),
                )
            ).Else(
                If(~self.delay[1],
                    self.decoder.input.eq(Cat(buffer, self.raw_input[1])),
                ).Else(
                    self.decoder.input.eq(Cat(buffer, self.delay_buf[1])),
                )
            ),
        ]

        self.comb += [
            self.d.eq(self.decoder.d),
            self.k.eq(self.decoder.k),
        ]


class SerdesSingle(Module, AutoCSR):
    def __init__(self, i_pads, o_pads, debug=False):
        # Modules for the IOB
        self.submodules.rx_phy = RXPhy(i_pads)
        self.submodules.tx_phy = TXPhy(o_pads)

        # Serdes Module
        self.submodules.rx_serdes = RXSerdes()
        self.submodules.tx_serdes = TXSerdes()

        # CSR for delay & bitslip
        self.bitslip_sel = CSRStorage(4)
        self.bitslip = CSR()

        for i in range(4):
            self.specials += MultiReg(
                self.bitslip_sel.storage[i] & self.bitslip.re,
                self.rx_serdes.bitslip[i], "eem_sys")
        
        self.dly_cnt_in_sel = CSRStorage(4)
        self.dly_cnt_in = CSRStorage(5)
        self.dly_ld = CSR()

        for i in range(4):
            self.comb += [
                self.rx_serdes.cnt_in[i].eq(self.dly_cnt_in.storage),
                self.rx_serdes.ld[i].eq(self.dly_cnt_in_sel.storage[i] & self.dly_ld.re),
            ]
        
        self.dly_cnt_out_sel = CSRStorage(4)
        self.dly_cnt_out = CSRStatus(5)

        self.comb += Case(self.dly_cnt_out_sel.storage, {
            (1 << idx): self.dly_cnt_out.status.eq(self.rx_serdes.cnt_out[idx]) for idx in range(4)
        })
        
        # CSR for global decoding phase
        # This is to determine if this cycle should decode SERDES 0 or 1
        self.decoder_dly = CSRStorage(4)
        dec_dly_cdc = Signal(4)
        self.specials += MultiReg(self.decoder_dly.storage, dec_dly_cdc, "eem_sys")

        # Encoder/Decodfer interfaces
        self.submodules.encoder = MultiEncoder()
        self.submodules.decoders = decoders = Array(CrossbarDecoder() for _ in range(2))

        # Wire up the IOB to serdes modules
        for i in range(4):
            self.comb += [
                self.tx_phy.i[i].eq(self.tx_serdes.ser_out[i]),
                self.tx_phy.t[i].eq(self.tx_serdes.t_out[i]),

                self.rx_serdes.ser_in_no_dly[i].eq(self.rx_phy.o[i]),
            ]
        
        # Control decoders phase
        self.comb += [
            decoders[0].delay.eq(dec_dly_cdc[:2]),
            decoders[1].delay.eq(dec_dly_cdc[2:]),
        ]
        
        # Route encoded symbols to TXSerdes
        self.comb += [
            self.tx_serdes.txdata[0].eq(self.encoder.output[0][:5]),
            self.tx_serdes.txdata[1].eq(self.encoder.output[0][5:]),
            self.tx_serdes.txdata[2].eq(self.encoder.output[1][:5]),
            self.tx_serdes.txdata[3].eq(self.encoder.output[1][5:]),
        ]

        # Truncate RX, controllable via CSR
        self.select_odd = CSRStorage(4)
        select_odd_cdc = Signal(4)
        self.specials += MultiReg(self.select_odd.storage, select_odd_cdc, "eem_sys")

        decimated_rxdata = [ Signal(5) for _ in range(4) ]
        for i in range(4):
            self.comb += decimated_rxdata[i].eq(Mux(select_odd_cdc[i],
                self.rx_serdes.rxdata[i][1::2], self.rx_serdes.rxdata[i][0::2]))
        
        # Route RXSerdes to decoder
        self.comb += [
            decoders[i//2].raw_input[i%2].eq(decimated_rxdata[i]) for i in range(4)
        ]

        # Always send out K.28.5 if not aligned
        self.send_align = CSRStorage(reset=1)
        self.specials += MultiReg(self.send_align.storage, self.encoder.align, "eem_sys")

        # Alternate phase
        phase = Signal()
        # Assign to encoder and decoder
        self.comb += [
            self.encoder.phase.eq(phase),
            self.decoders[0].phase.eq(phase),
            self.decoders[1].phase.eq(phase),
        ]

        # Phase increment & reset mechanism
        # Reset to 0 when externally triggered
        self.phase_rst = Signal()
        self.sync.eem_sys += If(self.phase_rst,
            phase.eq(0),
        ).Else(
            phase.eq(~phase)
        )
        self.phase_out = Signal()
        self.comb += self.phase_out.eq(phase)

        # Interleave data/ctrl update
        self.read_word = CSRStorage(2)
        self.aligned = CSRStatus()

        rx_d = Signal(8)
        rx_k = Signal()

        rx_d_prev = Signal(8)
        rx_k_prev = Signal()

        read_word_cdc = Signal(2)
        self.specials += MultiReg(self.read_word.storage, read_word_cdc)

        self.sync.eem_sys += [
            If(~phase ^ read_word_cdc[0],
                rx_d.eq(decoders[read_word_cdc[1]].d),
                rx_k.eq(decoders[read_word_cdc[1]].k),
                rx_d_prev.eq(rx_d),
                rx_k_prev.eq(rx_k),
            )
        ]

        found_align_symbol = Signal()
        self.comb += found_align_symbol.eq(
            (rx_d == 0xBC) & (rx_d_prev == 0xBC)
            & (rx_k == 1) & (rx_k_prev == 1))
        
        self.specials += MultiReg(found_align_symbol, self.aligned.status)


layout = [
    ("sat_clk_rdy", 2, "satellite"),
    ("phase_rdy",   3, "master"),
    ("sat_rst",     4, "master"),
    ("mst_clk_rdy", 5, "master"),
    ("align_mst",   6, "satellite"),
    ("align_sat",   7, "master"),
]

class EEMSerdes(Module, TransceiverInterface):    
    def __init__(self, platform, eem, eem_aux, role="master", start_idx=0):
        self.rx_ready = CSRStorage()

        # Request resources
        # TODO: Expand to support multiple EFCs
        i_pads = [
            platform.request("eem{}_fmc_data_in".format(eem), i) for i in range(4)
        ]
        o_pads = [
            platform.request("eem{}_fmc_data_out".format(eem), i) for i in range(4)
        ]

        self.submodules.serdes = SerdesSingle(i_pads, o_pads)
        self.submodules.aux = EEMAux(platform, eem_aux, role=role)
        
        # TODO: Move global phase here
        if role == "master":
            self.comb += self.aux.phase_in.eq(self.serdes.phase_out)
        elif role == "satellite":
            self.comb += self.serdes.phase_rst.eq(self.aux.phase_rst)
        
        chan_if = ChannelInterface(self.serdes.encoder, self.serdes.decoders)
        self.comb += chan_if.rx_ready.eq(self.rx_ready.storage)
        channel_interfaces = [chan_if]

        TransceiverInterface.__init__(self, channel_interfaces, start_idx=start_idx)

        self.comb += [
            getattr(self, "cd_rtio_rx" + str(start_idx)).clk.eq(ClockSignal("eem_sys")),
            getattr(self, "cd_rtio_rx" + str(start_idx)).rst.eq(ResetSignal("eem_sys"))
        ]


class EEMAux(Module, AutoCSR):
    def __init__(self, platform, eem_aux, role="master"):
        for name, _, src in layout:
            if name != "sat_rst":
                tmp = Signal()
                pad = platform.request(("eem{}_fmc_"+name).format(eem_aux))
                if src == role:
                    self.specials += DifferentialOutput(tmp, pad.p, pad.n)
                    setattr(self.submodules, name, gpio.GPIOOut(tmp))
                else:
                    self.specials += DifferentialInput(pad.p, pad.n, tmp)
                    setattr(self.submodules, name, gpio.GPIOIn(tmp))

        sat_rst_pad = platform.request("eem{}_fmc_sat_rst".format(eem_aux))
        sat_rst_tmp = Signal()
        if role == "master":
            self.phase_in = Signal()
            self.sat_phase_rst = CSR()
            sat_phase_rst_r = Signal()
            sat_phase_rst_rr = Signal()
            sat_phase_rst_cdc = Signal()

            self.specials += MultiReg(self.sat_phase_rst.re, sat_phase_rst_r, "eem_sys")
            self.sync.eem_sys += sat_phase_rst_rr.eq(sat_phase_rst_r)
            self.comb += sat_phase_rst_cdc.eq(sat_phase_rst_rr | sat_phase_rst_r)
            gated_pulse = Signal()
            self.sync.eem_sys += gated_pulse.eq(sat_phase_rst_cdc & self.phase_in)
            self.specials += DifferentialOutput(gated_pulse, sat_rst_pad.p, sat_rst_pad.n)

        elif role == "satellite":
            self.phase_rst = Signal()
            phase_in_raw = Signal()
            self.specials += DifferentialInput(sat_rst_pad.p, sat_rst_pad.n, phase_in_raw)
            self.specials += MultiReg(phase_in_raw, self.phase_rst, "eem_sys")
        else:
            ValueError("Invalid role type")
