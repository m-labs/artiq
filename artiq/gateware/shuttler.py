# Copyright 2013-2017 Robert Jordens <jordens@gmail.com>
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
from operator import add, or_

from migen import *
from misoc.interconnect.stream import Endpoint
from misoc.cores.cordic import Cordic
from artiq.gateware.rtio import rtlink


class Dac(Module):
    """Output module.

    Holds the two output line executors.

    Attributes:
        data (Signal[16]): Output value to be send to the DAC.
        clear (Signal): Clear accumulated phase offset when loading a new
                        waveform. Input.
        i (Endpoint[]): Coefficients of the output lines.
    """
    def __init__(self):
        self.clear = Signal()
        self.data = Signal(16)

        ###

        subs = [
            Volt(),
            Dds(self.clear),
        ]

        self.sync.rio += [
            self.data.eq(reduce(add, [sub.data for sub in subs])),
        ]

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
        self.i = Endpoint([("data", 16)])

        # This introduces 1 extra latency to everything in config
        # See the latency/delay attributes in Volt & DDS Endpoints/rtlinks
        self.sync.rio += If(self.i.stb, self.clr.eq(self.i.data))


Phy = namedtuple("Phy", "rtlink probes overrides")


class Shuttler(Module):
    """Shuttler module.

    Used both in functional simulation and final gateware.

    Holds the DACs and the configuration register. The DAC and Config are
    collected and adapted into RTIO interface.

    Attributes:
        phys (list): List of Endpoints.
    """
    def __init__(self):
        NUM_OF_DACS = 16

        self.phys = []

        self.submodules.cfg = Config()
        cfg_rtl_iface = rtlink.Interface(rtlink.OInterface(
            data_width=len(self.cfg.i.data),
            enable_replace=False))

        self.comb += [
            self.cfg.i.stb.eq(cfg_rtl_iface.o.stb),
            self.cfg.i.data.eq(cfg_rtl_iface.o.data),
        ]
        self.phys.append(Phy(cfg_rtl_iface, [], []))

        trigger_iface = rtlink.Interface(rtlink.OInterface(
            data_width=NUM_OF_DACS,
            enable_replace=False))
        self.phys.append(Phy(trigger_iface, [], []))

        for idx in range(NUM_OF_DACS):
            dac = Dac()
            self.comb += dac.clear.eq(self.cfg.clr[idx]),

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
