from collections import namedtuple
from migen import *
from misoc.cores.duc import PhasedAccuPipelined, CosSinGen, saturate
from migen.genlib.cdc import MultiReg, PulseSynchronizer
from migen.genlib.resetsync import AsyncResetSynchronizer
from misoc.interconnect.csr import AutoCSR, CSRStorage
from misoc.interconnect.stream import Endpoint
from artiq.gateware.rtio import rtlink
from artiq.gateware import rtio
from collections import namedtuple


class DDSClocks(Module):
    def __init__(self, rtio_clk_freq):
        self.mmcm_locked = Signal()
        self.mmcm_reset = Signal()

        ###
        
        self.clock_domains.cd_dds200 = ClockDomain()
        self.clock_domains.cd_dds600 = ClockDomain(reset_less=True)

        mmcm_fb_in = Signal()
        mmcm_fb_out = Signal()
        mmcm_dds200 = Signal()
        mmcm_dds600 = Signal()

        clk_mult = 12 if rtio_clk_freq == 100e6 else 10
        self.specials += [
            Instance("MMCME2_BASE",
                p_CLKIN1_PERIOD=1e9/rtio_clk_freq,
                i_CLKIN1=ClockSignal(),

                i_RST=ResetSignal() | self.mmcm_reset,

                i_CLKFBIN=mmcm_fb_in,
                o_CLKFBOUT=mmcm_fb_out,
                o_LOCKED=self.mmcm_locked,

                # VCO @ 1.2/1.25 with MULT=12/10
                p_CLKFBOUT_MULT_F=clk_mult, p_DIVCLK_DIVIDE=1,

                # 600/625MHz
                p_CLKOUT0_DIVIDE_F=2, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=mmcm_dds600,

                # 200/208.33MHz
                p_CLKOUT1_DIVIDE=6, p_CLKOUT1_PHASE=0.0, o_CLKOUT1=mmcm_dds200,

            ),
            Instance("BUFG", i_I=mmcm_dds200, o_O=self.cd_dds200.clk),
            Instance("BUFG", i_I=mmcm_dds600, o_O=self.cd_dds600.clk),
            Instance("BUFG", i_I=mmcm_fb_out, o_O=mmcm_fb_in),
            AsyncResetSynchronizer(self.cd_dds200, ~self.mmcm_locked)
        ]


class SumAndScale(Module):
    def __init__(self, n_dds):
        self.inputs = [Signal((16, True)) for _ in range(n_dds)]
        self.amplitudes = [Signal((16, True)) for _ in range(n_dds)]
        self.output = Signal((16, True))

        ###

        products = [Signal((32, True)) for _ in range(n_dds)]
        for i in range(n_dds):
            # First, multiply (preserving full 32-bit result)
            self.sync += products[i].eq(self.inputs[i] * self.amplitudes[i])

        # Then sum it all up
        sum_all = Signal((34, True))
        self.sync += sum_all.eq(sum(products))

        # Finally, shift and saturate
        scaled_sum = Signal((19, True))
        self.comb += scaled_sum.eq(sum_all[15:])

        self.sync += [
            If(scaled_sum > 0x7FFF,
                self.output.eq(0x7FFF)
            ).Elif(scaled_sum < -0x8000,
                self.output.eq(-0x8000)
            ).Else(
                self.output.eq(scaled_sum)
            )
        ]


class DoubleDataRateDDS(Module):
    """Composite DDS running at twice the system clock rate.
    """
    def __init__(self, n, fwidth, pwidth, x=15):
        self.ftw  = Signal(fwidth)
        self.ptw  = Signal(pwidth)
        self.clr  = Signal()

        # for loading the samples
        self.counter = Signal()
        # output data modified in dds200 domain
        self.dout2x = Signal((x+1)*n*2)

        ###

        # phased accu running in dds200 clock domain
        paccu = ClockDomainsRenamer("dds200")(PhasedAccuPipelined(n, fwidth, pwidth))
        self.submodules.clear = PulseSynchronizer("sys", "dds200")
        self.comb += [
            self.clear.i.eq(self.clr),
            paccu.clr.eq(self.clear.o)
        ]
        self.specials += [
            MultiReg(self.ftw, paccu.f, "dds200"),
            MultiReg(self.ptw, paccu.p, "dds200"),
        ]
        self.submodules += paccu
        dds0 = ClockDomainsRenamer("dds200")(CosSinGen())
    
        self.ddss = [dds0] + [ClockDomainsRenamer("dds200")(CosSinGen(share_lut=dds0.lut)) for _ in range(1, n)]

        for idx, dds in enumerate(self.ddss):
            setattr(self.submodules, f"dds{idx}", dds)
            self.comb += dds.z.eq(paccu.z[idx])

            self.sync.dds200 += [
                If(self.counter,
                    self.dout2x[idx*16:(idx+1)*16].eq(dds.x)
                ).Else(
                    self.dout2x[(idx+n)*16:(idx+n+1)*16].eq(dds.x)
                )
            ]


class SongbirdDDSModule(Module, AutoCSR):
    """The line data is interpreted as:
        
        Bs:
        * 16 bit amplitude offset
        * 32 bit amplitude first order derivative
        * 48 bit amplitude second order derivative
        * 48 bit amplitude third order derivative
        Cs:
        * 16 bit phase offset
        * 32 bit frequency word
        * 32 bit chirp
        * 16 bit shift + remaining phase bits
    """

    def __init__(self):
        self.clear = Signal()
        self.ftw = Signal(32)
        self.atw = Signal(32)
        self.ptw = Signal(18)
        self.amplitude = Signal(16)
        self.reset = Signal()

        self.shift = Signal(4)
        self.shift_counter = Signal(16) # Need to count from 2**shift - 1

        phase_msb_word = Signal(16)      # Upper 16 bits of 18-bit phase value
        control_word = Signal(16)        # Packed: shift[3:0] + phase_lsb[5:4] + reserved[15:6]
        reconstructed_phase = Signal(18)

        self.bs_i = Endpoint([("data", 16 + 32 + 48 + 48)])
        self.cs_i = Endpoint([("data", 16 + 32 + 32 + 16)])

        z = [Signal((32, True)) for i in range(3)] # phase, dphase, ddphase
        x = [Signal((48, True)) for i in range(4)] # amp, damp, ddamp, dddamp

        self.sync += [
            self.ftw.eq(z[1]),
            self.atw.eq(x[0]),
            self.ptw.eq(reconstructed_phase),

            If(self.reset,
                self.ftw.eq(0),
                self.atw.eq(0),
                self.ptw.eq(0),
                x[0].eq(0),
                x[1].eq(0),
                x[2].eq(0),
                x[3].eq(0),
                z[0].eq(0),
                z[1].eq(0),
                z[2].eq(0),
            ),

            # count down from 2**shift-1 to 0
            If(self.shift_counter == 0,
                Case(self.shift,
                    { i: self.shift_counter.eq((1 << i) - 1) for i in range(2**len(self.shift)) } | { "default": self.shift_counter.eq(0) }
                )
            ).Else(
                self.shift_counter.eq(self.shift_counter - 1)
            ),

            # Using shift here as a divider
            If(self.shift_counter == 0,
                x[0].eq(x[0] + x[1]),
                x[1].eq(x[1] + x[2]),
                x[2].eq(x[2] + x[3]),
                z[1].eq(z[1] + z[2]),
            ),

            If(self.bs_i.stb,
                x[0][:32].eq(0),
                x[1][:16].eq(0),
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
                control_word[4:6],  # Phase extension bits [5:4] become LSBs [1:0]
                phase_msb_word      # Main phase bits become MSBs [17:2]
            )),

            self.amplitude.eq(x[0][32:]),
            self.shift.eq(control_word[:4]),   # Shift value in bits [3:0]
        ]
        
        # 12 phases at 200/208.33 MHz => 2400/2500 MSPS
        self.submodules.dds = DoubleDataRateDDS(12, 32, 18)
        self.sync += [
            self.dds.ftw.eq(self.ftw),
            self.dds.ptw.eq(self.ptw),
            self.dds.clr.eq(self.clear)
        ]


class DataSynth(Module, AutoCSR):
    def __init__(self, n_dds, n_phases):
        self.amplitudes = Array([[Signal(16, name=f"amplitudes_{i}_{j}") for i in range(n_phases)] for j in range(n_dds)])
        self.data_in = Array([[Signal(16, name=f"data_in_{i}_{j}") for i in range(n_phases)] for j in range(n_dds)])
        self.ios = []

        self.summers = [ClockDomainsRenamer("dds200")(SumAndScale(n_dds)) for _ in range(n_phases)]
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

class Songbird(Module, AutoCSR):
    def __init__(self, platform, ltc2000_pads, clk_freq=125e6):
        n_dds = 4
        n_phases = 24

        self.submodules.dds_clock = DDSClocks(clk_freq)
        self.submodules.datasynth = DataSynth(n_dds, n_phases)

        self.tones = [SongbirdDDSModule() for _ in range(n_dds)]
        for idx, tone in enumerate(self.tones):
            setattr(self.submodules, f"tone{idx}", tone)

        self.phys = []

        platform.add_extension(ltc2000_pads)
        self.dac_pads = platform.request("ltc2000")
        self.submodules.ltc2000 = Ltc2000phy(self.dac_pads, clk_freq)

        counter = Signal()  # alternating sample loader, shared between Phy and DDS
        self.comb += self.ltc2000.counter.eq(counter)
        self.sync.dds200 += counter.eq(~counter)

        clear = Signal(n_dds)
        self.submodules.reset = PulseSynchronizer("rio", "dds200")

        self.comb += self.ltc2000.reset.eq(self.reset.o | ~self.dds_clock.mmcm_locked)

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
        reset_iface = rtlink.Interface(rtlink.OInterface(
            data_width=1,
            enable_replace=False))

        self.sync.rio += [
            If(reset_iface.o.stb,
                self.reset.i.eq(reset_iface.o.data),
                self.dds_clock.mmcm_reset.eq(reset_iface.o.data)
            )
        ]
        self.phys.append(Phy(reset_iface, [], [], 'reset_iface'))

        trigger_iface = rtlink.Interface(rtlink.OInterface(
            data_width=n_dds,
            address_width=1,  # address 0 for b trigger, 1 for c trigger
            enable_replace=False))
        self.phys.append(Phy(trigger_iface, [], [], 'trigger_iface'))

        for idx, tone in enumerate(self.tones):
            self.comb += [
                tone.clear.eq(clear[idx]),
                tone.dds.counter.eq(counter),
                tone.reset.eq(self.reset.i)
            ]

            bs_rtl_iface = rtlink.Interface(rtlink.OInterface(
                data_width=16, address_width=4))
            cs_rtl_iface = rtlink.Interface(rtlink.OInterface(
                data_width=16, address_width=3))

            bs_array = Array(tone.bs_i.data[wi: wi+16] for wi in range(0, len(tone.bs_i.data), 16))
            cs_array = Array(tone.cs_i.data[wi: wi+16] for wi in range(0, len(tone.cs_i.data), 16))

            self.sync.rio += [
                tone.bs_i.stb.eq(self.reset.i | ((trigger_iface.o.address == 0) &
                                 trigger_iface.o.data[idx] & 
                                 trigger_iface.o.stb)),
                If(bs_rtl_iface.o.stb,
                    bs_array[bs_rtl_iface.o.address].eq(bs_rtl_iface.o.data),
                ),
                tone.cs_i.stb.eq(self.reset.i | ((trigger_iface.o.address == 1) &
                                 trigger_iface.o.data[idx] & 
                                 trigger_iface.o.stb)),
                If(cs_rtl_iface.o.stb,
                    cs_array[cs_rtl_iface.o.address].eq(cs_rtl_iface.o.data),
                ),
            ]

            self.phys.append(Phy(bs_rtl_iface, [], [], f'dds{idx}_bs_iface'))
            self.phys.append(Phy(cs_rtl_iface, [], [], f'dds{idx}_cs_iface'))

        for i in range(n_phases):
            # summers are in dds200 clock domain
            self.comb += self.ltc2000.data[i*16:(i+1)*16].eq(self.datasynth.summers[i].output)
            for j in range(n_dds):
                self.comb += [
                    self.datasynth.data_in[j][i].eq(self.tones[j].dds.dout2x[i*16:(i+1)*16]),
                    self.datasynth.amplitudes[j][i].eq(self.tones[j].amplitude)
                ]


class Ltc2000phy(Module, AutoCSR):
    def __init__(self, pads, clk_freq=125e6):
        self.data = Signal(16*24) # 16 bits per channel, 24 phases input

        self.reset = Signal()
        self.counter = Signal()

        ###

        # 16 bits per channel, 2 channels, 6 samples per clock cycle, data coming in at dds200 rate
        # for 125 MHz sysclk it's 208.33MHz * 2 * 6 = 2.5 Gbps
        data_in = Signal(16*2*6)

        # Load data into register, swapping halves
        self.sync.dds200 += [
            If(self.counter,
                data_in.eq(self.data[:16*2*6])
            ).Else(
                data_in.eq(self.data[16*2*6:])
            ),
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

