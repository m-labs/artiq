from artiq.gateware import rtio
from migen import *
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from misoc.interconnect.csr import AutoCSR, CSRStorage
from misoc.interconnect.stream import Endpoint
from artiq.gateware.rtio import rtlink
from misoc.cores.duc import PhasedAccuPipelined, CosSinGen, saturate
from collections import namedtuple

class SumAndScale(Module):
    def __init__(self):
        self.inputs = [Signal((16, True)) for _ in range(4)]
        self.amplitudes = [Signal((16, True)) for _ in range(4)]
        self.output = Signal((16, True))

        ###

        products = [Signal((32, True)) for _ in range(4)]
        for i in range(4):
            # First, multiply (preserving full 32-bit result)
            self.sync += products[i].eq(self.inputs[i] * self.amplitudes[i])

        # Sum the full 32-bit results
        sum_all = Signal((34, True))  # Extra bits to avoid potential overflow
        self.comb += sum_all.eq(products[0] + products[1] + products[2] + products[3])

        # Finally, shift and saturate
        self.sync += [
            If(sum_all[15:] > 0x7FFF,
                self.output.eq(0x7FFF)
            ).Elif(sum_all[15:] < -0x8000,
                self.output.eq(-0x8000)
            ).Else(
                self.output.eq(sum_all[15:])
            )
        ]

class PolyphaseDDS(Module):
    """Composite DDS with sub-DDSs synthesizing
       individual phases to increase fmax.
    """
    def __init__(self, n, fwidth, pwidth, x=15):
        self.ftw  = Signal(fwidth)
        self.ptw  = Signal(pwidth)
        self.clr  = Signal()
        self.dout = Signal((x+1)*n)

        ###

        paccu = PhasedAccuPipelined(n, fwidth, pwidth)
        self.comb += paccu.clr.eq(self.clr)
        self.comb += paccu.f.eq(self.ftw)
        self.comb += paccu.p.eq(self.ptw)
        self.submodules.paccu = paccu
        ddss = [CosSinGen() for i in range(n)]
        for idx, dds in enumerate(ddss):
            self.submodules += dds
            self.comb += dds.z.eq(paccu.z[idx])
            self.comb += self.dout[idx*16:(idx+1)*16].eq(dds.y)


class DoubleDataRateDDS(Module):
    """Composite DDS running at twice the system clock rate.
    """
    def __init__(self, n, fwidth, pwidth, x=15):
        self.ftw  = Signal(fwidth)
        self.ptw  = Signal(pwidth)
        self.clr  = Signal()
        self.dout = Signal((x+1)*n*2)

        ###

        paccu = ClockDomainsRenamer("dds200")(PhasedAccuPipelined(n, fwidth, pwidth)) # Running this at 2x clock speed
        self.submodules.clear = PulseSynchronizer("sys", "dds200")
        self.comb += [
            self.clear.i.eq(self.clr),
            paccu.clr.eq(self.clear.o)
        ]
        self.specials += [
            MultiReg(self.ftw, paccu.f, "dds200"),
            MultiReg(self.ptw, paccu.p, "dds200"),
        ]
        self.submodules.paccu = paccu
        self.ddss = [ClockDomainsRenamer("dds200")(CosSinGen()) for _ in range(n)]
        counter = Signal()
        dout2x = Signal((x+1)*n*2)  # output data modified in 2x domain
        for idx, dds in enumerate(self.ddss):
            setattr(self.submodules, f"dds{idx}", dds)
            self.comb += dds.z.eq(paccu.z[idx])

            self.sync.dds200 += [
                If(counter,
                    dout2x[idx*16:(idx+1)*16].eq(dds.x)
                ).Else(
                    dout2x[(idx+n)*16:(idx+n+1)*16].eq(dds.x)
                ),
                counter.eq(~counter)
            ]
        self.specials += MultiReg(dout2x, self.dout)


class LTC2000DDSModule(Module, AutoCSR):
    """The line data is interpreted as:

        * 16 bit amplitude offset
        * 32 bit amplitude first order derivative
        * 48 bit amplitude second order derivative
        * 48 bit amplitude third order derivative
        * 16 bit phase offset
        * 32 bit frequency word
        * 32 bit chirp
    """

    def __init__(self):
        NPHASES = 12
        self.clear = Signal()
        self.ftw = Signal(32)
        self.atw = Signal(32)
        self.ptw = Signal(18)
        self.amplitude = Signal(16)
        self.gain = Signal(16)

        self.shift = Signal(4)
        self.shift_counter = Signal(16) # Need to count to 2**shift - 1
        self.shift_stb = Signal()

        phase_msb_word = Signal(16)      # Upper 16 bits of 18-bit phase value
        control_word = Signal(16)        # Packed: shift[3:0] + phase_lsb[5:4] + reserved[15:6]
        reconstructed_phase = Signal(18)

        self.reserved = Signal(12) # for future use

        self.bs_i = Endpoint([("data", 144)])
        self.cs_i = Endpoint([("data", 96)])

        self.comb += [
            self.shift_stb.eq((self.shift == 0) |
                             (self.shift_counter == (1 << self.shift) - 1)) # power of two for strobing
        ]
        self.sync += [
            If(self.shift == 0,
                self.shift_counter.eq(0)
            ).Elif(self.shift_counter == (1 << self.shift) - 1,
                self.shift_counter.eq(0)
            ).Else(
                self.shift_counter.eq(self.shift_counter + 1)
            )
        ]

        z = [Signal(32) for i in range(3)] # phase, dphase, ddphase
        x = [Signal(48) for i in range(4)] # amp, damp, ddamp, dddamp

        self.sync += [
            self.ftw.eq(z[1]),
            self.atw.eq(x[0]),
            self.ptw.eq(reconstructed_phase),

            # Using shift here as a divider
            If(self.shift_stb,
                x[0].eq(x[0] + x[1]),
                x[1].eq(x[1] + x[2]),
                x[2].eq(x[2] + x[3]),
                z[1].eq(z[1] + z[2]),
            ),

            If(self.bs_i.stb,
                x[0].eq(0),
                x[1].eq(0),
                Cat(x[0][32:],           # b0: amp offset (16 bits)
                    x[1][16:],           # b1: damp (32 bits)
                    x[2],                # b2: ddamp (48 bits)
                    x[3]                 # b3: dddamp (48 bits)
                ).eq(self.bs_i.payload.raw_bits()),
                self.shift_counter.eq(0),
            ),
            If(self.cs_i.stb,
                Cat(
                    phase_msb_word,      # phase main (16 bits) - Word 9
                    z[1],                # ftw (32 bits) - Words 10-11
                    z[2],                # chirp (32 bits) - Words 12-13
                    control_word,        # control word (16 bits) - Word 14
                ).eq(self.cs_i.payload.raw_bits()),
                self.shift_counter.eq(0),
            ),
        ]

        self.comb += [
            # Reconstruct 18-bit phase with extension bits in correct position
            reconstructed_phase.eq(Cat(
                control_word[5],
                control_word[4],                # Phase extension bits [5:4] become LSBs [1:0]
                phase_msb_word                  # Main phase bits become MSBs [17:2]
            )),

            self.shift.eq(Cat(
                control_word[3],
                control_word[2],
                control_word[1],
                control_word[0]
            )),   # Shift value in bits [3:0]

            self.amplitude.eq(x[0][32:])
        ]
        
        # 12 phases at 200/208.33 MHz => 2400/2500 MSPS
        # output updated at 100/125 MHz
        self.submodules.dds = DoubleDataRateDDS(NPHASES, 32, 18)
        self.sync += [
            self.dds.ftw.eq(self.ftw),
            self.dds.ptw.eq(self.ptw),
            self.dds.clr.eq(self.clear)
        ]


class LTC2000DataSynth(Module, AutoCSR):
    def __init__(self, n_dds, n_phases):
        self.amplitudes = Array([[Signal(16, name=f"amplitudes_{i}_{j}") for i in range(n_phases)] for j in range(n_dds)])
        self.data_in = Array([[Signal(16, name=f"data_in_{i}_{j}") for i in range(n_phases)] for j in range(n_dds)])
        self.ios = []

        self.summers = [SumAndScale() for _ in range(n_phases)]
        for idx, summer in enumerate(self.summers):
            setattr(self.submodules, f"summer{idx}", summer)

        for i in range(n_phases):
            for j in range(n_dds):
                self.ios.append(self.amplitudes[j][i])
                self.ios.append(self.data_in[j][i])
                self.comb += [
                    self.summers[i].inputs[j].eq(self.data_in[j][i]),
                    self.summers[i].amplitudes[j].eq(self.amplitudes[j][i]),
                ]

Phy = namedtuple("Phy", "rtlink probes overrides name")

class LTC2000(Module, AutoCSR):
    def __init__(self, platform, ltc2000_pads, clk_freq=125e6):
        n_dds = 4
        n_phases = 24

        self.submodules.ltc2000datasynth = LTC2000DataSynth(n_dds, n_phases)

        self.tones = [LTC2000DDSModule() for _ in range(n_dds)]
        for idx, tone in enumerate(self.tones):
            setattr(self.submodules, f"tone{idx}", tone)

        self.phys = []

        platform.add_extension(ltc2000_pads)
        self.dac_pads = platform.request("ltc2000")
        self.submodules.ltc2000 = Ltc2000phy(self.dac_pads, clk_freq)

        clear = Signal(n_dds)
        self.submodules.reset = PulseSynchronizer("rio", "dds200")

        self.comb += self.ltc2000.reset.eq(self.reset.o)

        gain_iface = rtlink.Interface(rtlink.OInterface(
            data_width=16,
            address_width=4,
            enable_replace=False
        ))
        self.phys.append(Phy(gain_iface, [], [], 'gain_iface'))

        tone_gains = Array([tone.gain for tone in self.tones])
        self.sync.rio += [
            If(gain_iface.o.stb,
                tone_gains[gain_iface.o.address].eq(gain_iface.o.data)
            )
        ]

        clear_iface = rtlink.Interface(rtlink.OInterface(
            data_width=n_dds,
            enable_replace=False
        ))
        self.phys.append(Phy(clear_iface, [], [], 'clear_iface'))

        self.sync.rio += [
            If(clear_iface.o.stb,
                clear.eq(clear_iface.o.data)
            )
        ]

        bs_trigger_iface = rtlink.Interface(rtlink.OInterface(
            data_width=n_dds,
            enable_replace=False))
        cs_trigger_iface = rtlink.Interface(rtlink.OInterface(
            data_width=n_dds,
            enable_replace=False))

        reset_iface = rtlink.Interface(rtlink.OInterface(
            data_width=1,
            enable_replace=False))

        self.sync.rio += [
            If(reset_iface.o.stb,
                self.reset.i.eq(reset_iface.o.data)
            )
        ]
        self.phys.append(Phy(reset_iface, [], [], 'reset_iface'))

        for idx, tone in enumerate(self.tones):
            self.comb += [
                tone.clear.eq(clear[idx]),
            ]

            bs_rtl_iface = rtlink.Interface(rtlink.OInterface(
                data_width=16, address_width=4))
            cs_rtl_iface = rtlink.Interface(rtlink.OInterface(
                data_width=16, address_width=3))

            bs_array = Array(tone.bs_i.data[wi: wi+16] for wi in range(0, len(tone.bs_i.data), 16))
            cs_array = Array(tone.cs_i.data[wi: wi+16] for wi in range(0, len(tone.cs_i.data), 16))

            self.sync.rio += [
                tone.bs_i.stb.eq(bs_trigger_iface.o.data[idx] & bs_trigger_iface.o.stb),
                If(bs_rtl_iface.o.stb,
                    bs_array[bs_rtl_iface.o.address].eq(bs_rtl_iface.o.data),
                ),
                tone.cs_i.stb.eq(cs_trigger_iface.o.data[idx] & cs_trigger_iface.o.stb),
                If(cs_rtl_iface.o.stb,
                    cs_array[cs_rtl_iface.o.address].eq(cs_rtl_iface.o.data),
                ),
            ]

            self.phys.append(Phy(bs_rtl_iface, [], [], f'dds{idx}_bs_iface'))
            self.phys.append(Phy(cs_rtl_iface, [], [], f'dds{idx}_cs_iface'))

        for i in range(n_phases):
            for j in range(n_dds):
                self.comb += [
                    self.ltc2000datasynth.data_in[j][i].eq(self.tones[j].dds.dout[i*16:(i+1)*16]),
                    self.ltc2000datasynth.amplitudes[j][i].eq(self.tones[j].amplitude)
                ]

        self.specials += [
            MultiReg(self.ltc2000datasynth.summers[i].output, self.ltc2000.data[i*16:(i+1)*16], "dds200")
            for i in range (n_phases)
        ]

        self.phys.append(Phy(bs_trigger_iface, [], [], 'bs_trigger_iface'))
        self.phys.append(Phy(cs_trigger_iface, [], [], 'cs_trigger_iface'))


class Ltc2000phy(Module, AutoCSR):
    def __init__(self, pads, clk_freq=125e6):
        self.data = Signal(16*24) # 16 bits per channel, 24 phases input at sys clock rate
        self.reset = Signal()

        ###

        # 16 bits per channel, 2 channels, 6 samples per clock cycle, data coming in at dds200 rate
        # for 100 MHz sysclk we get 200 MHz * 2 * 6 = 2.4 Gbps
        # for 125 MHz sysclk it's 208.33MHz * 2 * 6 = 2.5 Gbps
        data_in = Signal(16*2*6) 
        counter = Signal()

        # Load data into register, swapping halves
        self.sync.dds200 += [
            If(~counter,
                data_in.eq(self.data[16*2*6:])  # Load second half first
            ).Else(
                data_in.eq(self.data[:16*2*6])  # Load first half second
            ),
            counter.eq(~counter)
        ]

        dac_clk_se = Signal()
        dac_data_se = Signal(16)
        dac_datb_se = Signal(16)

        self.specials += [
            Instance("OSERDESE2",
                p_DATA_WIDTH=6, p_TRISTATE_WIDTH=1,
                p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                p_SERDES_MODE="MASTER",

                o_OQ=dac_clk_se,
                i_OCE=1,
                i_RST=self.reset,
                i_CLK=ClockSignal("dds600"), i_CLKDIV=ClockSignal("dds200"),
                i_D1=1, i_D2=0, i_D3=1, i_D4=0,
                i_D5=1, i_D6=0,
            ),
            Instance("OBUFDS",
                i_I=dac_clk_se,
                o_O=pads.clk_p,
                o_OB=pads.clk_n
            )
        ]

        for i in range(16):
            self.specials += [
                Instance("OSERDESE2",
                    p_DATA_WIDTH=6, p_TRISTATE_WIDTH=1,
                    p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                    p_SERDES_MODE="MASTER",

                    o_OQ=dac_data_se[i],
                    i_OCE=1,
                    i_RST=self.reset,
                    i_CLK=ClockSignal("dds600"), i_CLKDIV=ClockSignal("dds200"),
                    i_D1=data_in[0*16 + i], i_D2=data_in[2*16 + i],
                    i_D3=data_in[4*16 + i], i_D4=data_in[6*16 + i],
                    i_D5=data_in[8*16 + i], i_D6=data_in[10*16 + i]
                ),
                Instance("OBUFDS",
                    i_I=dac_data_se[i],
                    o_O=pads.data_p[i],
                    o_OB=pads.data_n[i]
                ),
                Instance("OSERDESE2",
                    p_DATA_WIDTH=6, p_TRISTATE_WIDTH=1,
                    p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                    p_SERDES_MODE="MASTER",

                    o_OQ=dac_datb_se[i],
                    i_OCE=1,
                    i_RST=self.reset,
                    i_CLK=ClockSignal("dds600"), i_CLKDIV=ClockSignal("dds200"),
                    i_D1=data_in[1*16 + i], i_D2=data_in[3*16 + i],
                    i_D3=data_in[5*16 + i], i_D4=data_in[7*16 + i],
                    i_D5=data_in[9*16 + i], i_D6=data_in[11*16 + i]
                ),
                Instance("OBUFDS",
                    i_I=dac_datb_se[i],
                    o_O=pads.datb_p[i],
                    o_OB=pads.datb_n[i]
                )
        ]
