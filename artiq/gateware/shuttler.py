# Copyright 2013-2017 Robert Jordens <jordens@gmail.com>
#
# shuttler is developed based on pdq.
#
# pdq is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pdq is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pdq.  If not, see <http://www.gnu.org/licenses/>.

from collections import namedtuple
from operator import add

from migen import *
from misoc.interconnect.stream import Endpoint
from misoc.interconnect.csr import *
from misoc.cores.cordic import Cordic
from artiq.gateware.rtio import rtlink

class DacInterface(Module, AutoCSR):
    def __init__(self, pads):
        bit_width = len(pads[0].data)

        self.data = [[Signal(bit_width) for _ in range(2)] for _ in range(8)]

        self.ddr_clk_phase_shift = CSR()
        self.ddr_clk_phase_shift_done = CSRStatus(reset=1)

        mmcm_ps_fb = Signal()
        mmcm_ps_output = Signal()
        mmcm_ps_psdone = Signal()
        ddr_clk = Signal()

        # Generate DAC DDR CLK
        # 125MHz to 125MHz with controllable phase shift,
        # VCO @ 1000MHz.
        # Phase is shifted by 45 degree by default
        self.specials += \
            Instance("MMCME2_ADV",
                p_CLKIN1_PERIOD=8.0,
                i_CLKIN1=ClockSignal(),
                i_RST=ResetSignal(),
                i_CLKINSEL=1, 

                p_CLKFBOUT_MULT_F=8.0,
                p_CLKOUT0_DIVIDE_F=8.0,
                p_DIVCLK_DIVIDE=1,
                p_CLKOUT0_PHASE=45.0,

                o_CLKFBOUT=mmcm_ps_fb, i_CLKFBIN=mmcm_ps_fb,

                p_CLKOUT0_USE_FINE_PS="TRUE",
                o_CLKOUT0=mmcm_ps_output,

                i_PSCLK=ClockSignal(),
                i_PSEN=self.ddr_clk_phase_shift.re,
                i_PSINCDEC=self.ddr_clk_phase_shift.r,
                o_PSDONE=mmcm_ps_psdone,
            )

        self.sync += [
            If(self.ddr_clk_phase_shift.re, self.ddr_clk_phase_shift_done.status.eq(0)),
            If(mmcm_ps_psdone, self.ddr_clk_phase_shift_done.status.eq(1))
        ]

        # din.clk pads locate at multiple clock regions/IO banks
        self.specials += [
            Instance("BUFG", i_I=mmcm_ps_output, o_O=ddr_clk),
        ]

        for i, din in enumerate(pads):
            self.specials += Instance("ODDR", 
                    i_C=ddr_clk, 
                    i_CE=1, 
                    i_D1=1, 
                    i_D2=0, 
                    o_Q=din.clk,
                    p_DDR_CLK_EDGE="SAME_EDGE")
            self.specials += [
                Instance("ODDR", 
                    i_C=ClockSignal(), 
                    i_CE=1, 
                    i_D1=self.data[i][0][bit], # DDR CLK Rising Edge
                    i_D2=self.data[i][1][bit], # DDR CLK Falling Edge
                    o_Q=din.data[bit],
                    p_DDR_CLK_EDGE="SAME_EDGE") 
                for bit in range(bit_width)]


class SigmaDeltaModulator(Module):
    """First order Sigma-Delta modulator."""
    def __init__(self, x_width, y_width):
        self.x = Signal(x_width)
        self.y = Signal(y_width)

        # SDM can at most output the max DAC code `Replicate(1, y_width-1)`,
        # which represents the sample of value
        # `Replicate(1, y_width-1) << (x_width-y_width)`.
        #
        # If the input sample exceeds such limit, SDM may overflow.
        x_capped = Signal(x_width)
        max_dac_code = Replicate(1, (y_width-1))
        self.comb += If(self.x[x_width-y_width:] == max_dac_code,
            x_capped.eq(Cat(Replicate(0, x_width-y_width), max_dac_code)),
        ).Else(
            x_capped.eq(self.x),
        )

        acc = Signal(x_width)

        self.comb += self.y.eq(acc[x_width-y_width:])
        self.sync.rio += acc.eq(x_capped - Cat(Replicate(0, x_width-y_width), self.y) + acc)


class Dac(Module):
    """Output module.

    Holds the two output line executors.

    Attributes:
        data (Signal[14]): Output value to be send to the DAC.
        clear (Signal): Clear accumulated phase offset when loading a new
                        waveform. Input.
        gain (Signal[16]): Output value gain. The gain signal represents the
                           decimal part os the gain in 2's complement.
        offset (Signal[16]): Output value offset.
        i (Endpoint[]): Coefficients of the output lines.
    """
    def __init__(self, sdm=False):
        self.clear = Signal()
        self.data = Signal(14)
        self.gain = Signal(16)
        self.offset = Signal(16)

        overflow = Signal()
        underflow = Signal()

        ###

        subs = [
            Volt(),
            Dds(self.clear),
        ]

        # Infer signed multiplication
        data_raw = Signal((16, True))
        # Buffer data should have 2 more bits than the desired output width
        # It is to perform overflow/underflow detection
        data_buf = Signal(18)
        data_sink = Signal(16)

        if sdm:
            self.submodules.sdm = SigmaDeltaModulator(16, 14)

        self.sync.rio += [
            data_raw.eq(reduce(add, [sub.data for sub in subs])),
            # Extra buffer for timing for the DSP
            data_buf.eq(((data_raw * Cat(self.gain, ~self.gain[-1])) + (self.offset << 16))[16:]),
            If(overflow,
                data_sink.eq(0x7fff),
            ).Elif(underflow,
                data_sink.eq(0x8000),
            ).Else(
                data_sink.eq(data_buf),
            ),
        ]

        self.comb += [
            # Overflow condition
            overflow.eq(~data_buf[-1] & (data_buf[-2] | data_buf[-3])),
            # Underflow condition
            underflow.eq(data_buf[-1] & (~data_buf[-2] | ~data_buf[-3])),
        ]

        if sdm:
            self.comb += [
                self.sdm.x.eq(data_sink),
                self.data.eq(self.sdm.y),
            ]
        else:
            self.comb += self.data.eq(data_sink[2:])

        self.i = [ sub.i for sub in subs ]
        self.submodules += subs


class Volt(Module):
    """DC bias spline interpolator.

    The line data is interpreted as a concatenation of:

        * 16 bit amplitude offset
        * 32 bit amplitude first order derivative
        * 48 bit amplitude second order derivative
        * 48 bit amplitude third order derivative

    Attributes:
        data (Signal[16]): Output data from this spline.
        i (Endpoint): Coefficients of the DC bias spline, along with its
                        latency compensation.
    """
    def __init__(self):
        self.data = Signal(16)
        self.i = Endpoint([("data", 144)])
        self.i.latency = 17

        ###

        v = [Signal(48) for i in range(4)] # amp, damp, ddamp, dddamp

        # Increase latency of stb by 17 cycles to compensate CORDIC latency
        stb_r = [ Signal() for _ in range(17) ]
        self.sync.rio += [
            stb_r[0].eq(self.i.stb),
        ]
        for idx in range(16):
            self.sync.rio += stb_r[idx+1].eq(stb_r[idx])

        self.sync.rio += [
            v[0].eq(v[0] + v[1]),
            v[1].eq(v[1] + v[2]),
            v[2].eq(v[2] + v[3]),
            If(stb_r[16],
                v[0].eq(0),
                v[1].eq(0),
                Cat(v[0][32:], v[1][16:], v[2], v[3]).eq(self.i.payload.raw_bits()),
            )
        ]
        self.comb += self.data.eq(v[0][32:])


class Dds(Module):
    """DDS spline interpolator.

    The line data is interpreted as:

        * 16 bit amplitude offset
        * 32 bit amplitude first order derivative
        * 48 bit amplitude second order derivative
        * 48 bit amplitude third order derivative
        * 16 bit phase offset
        * 32 bit frequency word
        * 32 bit chirp

    Args:
        line (Record[line_layout]): Next line to be executed. Input.
        clear (Signal): Clear accumulated phase offset when loading a new
                        waveform. Input.

    Attributes:
        data (Signal[16]): Output data from this spline.
        i (Endpoint): Coefficients of the DDS spline, along with its latency
                        compensation.
    """
    def __init__(self, clear):
        self.data = Signal(16)
        self.i = Endpoint([("data", 224)])

        ###

        self.submodules.cordic = Cordic(width=16, eval_mode="pipelined",
                guard=None)

        za = Signal(32)
        z = [Signal(32) for i in range(3)] # phase, dphase, ddphase
        x = [Signal(48) for i in range(4)] # amp, damp, ddamp, dddamp
        self.comb += [
            self.cordic.xi.eq(x[0][32:]),
            self.cordic.yi.eq(0),
            self.cordic.zi.eq(za[16:] + z[0][16:]),
            self.data.eq(self.cordic.xo),
        ]

        self.sync.rio += [
            za.eq(za + z[1]),
            x[0].eq(x[0] + x[1]),
            x[1].eq(x[1] + x[2]),
            x[2].eq(x[2] + x[3]),
            z[1].eq(z[1] + z[2]),
            If(self.i.stb,
                x[0].eq(0),
                x[1].eq(0),
                Cat(x[0][32:], x[1][16:], x[2], x[3], z[0][16:], z[1], z[2]
                    ).eq(self.i.payload.raw_bits()),
                If(clear,
                    za.eq(0),
                )
            )
        ]


class Config(Module):
    def __init__(self):
        self.clr = Signal(16, reset=0xFFFF)
        self.gain = [ Signal(16) for _ in range(16) ]
        self.offset = [ Signal(16) for _ in range(16) ]

        reg_file = Array(self.gain + self.offset + [self.clr])
        self.i = Endpoint([
            ("data", 16),
            ("addr",  7),
        ])
        self.o = Endpoint([
            ("data", 16),
        ])

        # This introduces 1 extra latency to everything in config
        # See the latency/delay attributes in Volt & DDS Endpoints/rtlinks
        #
        # Gain & offsets are intended for initial calibration only, latency
        # is NOT adjusted to match outputs to the DAC interface
        #
        # Interface address bits mapping:
        # 6: Read bit. Assert to read, deassert to write.
        # 5: Clear bit. Assert to write clr. clr is write-only.
        # 4: Gain/Offset. (De)Assert to access (Gain)Offset registers.
        # 0-3: Channel selection for the Gain & Offset registers.
        #
        # Reading Gain / Offset register generates an RTIOInput event
        self.sync.rio += [
            self.o.stb.eq(0),
            If(self.i.stb,
                If(~self.i.addr[6],
                    reg_file[self.i.addr[:6]].eq(self.i.data),
                ).Else(
                    # clr register is unreadable, as an optimization
                    self.o.data.eq(reg_file[self.i.addr[:5]]),
                    self.o.stb.eq(1),
                )
            ),
        ]


Phy = namedtuple("Phy", "rtlink probes overrides")


class Shuttler(Module, AutoCSR):
    """Shuttler module.

    Used both in functional simulation and final gateware.

    Holds the DACs and the configuration register. The DAC and Config are
    collected and adapted into RTIO interface.

    Attributes:
        phys (list): List of Endpoints.
    """
    def __init__(self, pads, sdm=False):
        NUM_OF_DACS = 16

        self.submodules.dac_interface = DacInterface(pads)

        self.phys = []

        self.submodules.cfg = Config()
        cfg_rtl_iface = rtlink.Interface(
            rtlink.OInterface(
                data_width=len(self.cfg.i.data),
                address_width=len(self.cfg.i.addr),
                enable_replace=False,
            ),
            rtlink.IInterface(
                data_width=len(self.cfg.o.data),
            ),
        )

        self.comb += [
            self.cfg.i.stb.eq(cfg_rtl_iface.o.stb),
            self.cfg.i.addr.eq(cfg_rtl_iface.o.address),
            self.cfg.i.data.eq(cfg_rtl_iface.o.data),
            cfg_rtl_iface.i.stb.eq(self.cfg.o.stb),
            cfg_rtl_iface.i.data.eq(self.cfg.o.data),
        ]
        self.phys.append(Phy(cfg_rtl_iface, [], []))

        trigger_iface = rtlink.Interface(rtlink.OInterface(
            data_width=NUM_OF_DACS,
            enable_replace=False))
        self.phys.append(Phy(trigger_iface, [], []))

        for idx in range(NUM_OF_DACS):
            dac = Dac(sdm=sdm)
            self.comb += [
                dac.clear.eq(self.cfg.clr[idx]),
                dac.gain.eq(self.cfg.gain[idx]),
                dac.offset.eq(self.cfg.offset[idx]),
                self.dac_interface.data[idx // 2][idx % 2].eq(dac.data)
            ]

            for i in dac.i:
                delay = getattr(i, "latency", 0)
                rtl_iface = rtlink.Interface(rtlink.OInterface(
                    data_width=16, address_width=4, delay=delay))
                array = Array(i.data[wi: wi+16] for wi in range(0, len(i.data), 16))

                self.sync.rio += [
                    i.stb.eq(trigger_iface.o.data[idx] & trigger_iface.o.stb),
                    If(rtl_iface.o.stb,
                        array[rtl_iface.o.address].eq(rtl_iface.o.data),
                    ),
                ]

                self.phys.append(Phy(rtl_iface, [], []))

            self.submodules += dac
