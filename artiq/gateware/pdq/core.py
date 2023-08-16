# Copyright 2013-2017 Robert Jordens <jordens@gmail.com>
#
# This file is part of pdq.
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

        self.sync += [
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

        ###

        v = [Signal(48) for i in range(4)] # amp, damp, ddamp, dddamp

        self.sync += [
            v[0].eq(v[0] + v[1]),
            v[1].eq(v[1] + v[2]),
            v[2].eq(v[2] + v[3]),
            If(self.i.stb,
                v[0].eq(0),
                v[1].eq(0),
                Cat(v[0][32:], v[1][16:], v[2], v[3]).eq(self.i.data),
            )
        ]
        self.comb += self.data.eq(v[0][32:])

        # Compensate for Cordic & control registers
        self.i.latency = 18


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
        self.sync += [
            za.eq(za + z[1]),
            x[0].eq(x[0] + x[1]),
            x[1].eq(x[1] + x[2]),
            x[2].eq(x[2] + x[3]),
            z[1].eq(z[1] + z[2]),
            If(self.i.stb,
                x[0].eq(0),
                x[1].eq(0),
                Cat(x[0][32:], x[1][16:], x[2], x[3], z[0][16:], z[1], z[2]
                    ).eq(self.i.data),
                If(clear,
                    za.eq(0),
                )
            )
        ]

        # Compensate for control registers
        self.i.latency = 1


class Config(Module):
    def __init__(self):
        self.clr = Signal(16, reset=0xFFFF)
        self.i = Endpoint([("data", 16)])

        # This introduces 1 extra latency to everything in config
        # See the latency/delay attributes in Volt & DDS Endpoints/rtlinks
        self.sync += If(self.i.stb, self.clr.eq(self.i.data))


# TODO: REMOVE
class ShuttlerMonitor(Module):
    def __init__(self, dac):
        # Logger interface:
        # Select channel by address
        # Create input event by pulsing OInterface stb
        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=0),
            rtlink.IInterface(data_width=16),
        )

        stb_r = [ Signal() for _ in range(48) ]
        self.sync += stb_r[0].eq(self.rtlink.o.stb)
        for i in range(47):
            self.sync += stb_r[i+1].eq(stb_r[i])
        
        i_stb = Signal()
        self.comb += i_stb.eq(reduce(or_, stb_r))

        self.comb += [
            self.rtlink.i.stb.eq(i_stb),
            self.rtlink.i.data.eq(dac.data),
        ]


_Phy = namedtuple("Phy", "rtlink probes overrides")


class Pdq(Module):
    """PDQ module.

    Used both in functional simulation and final gateware.

    Holds the :mod:`gateware.dac.Dac`s and the configuration register. The
    DAC and Config are collected and to be adapted into RTIO interface.

    Attributes:
        phys (list): List of Endpoints.
    """
    def __init__(self):
        self.phys = []

        self.submodules.cfg = Config()
        cfg_rtl_iface = rtlink.Interface(rtlink.OInterface(
            data_width=len(self.cfg.i.data),
            enable_replace=False))

        self.comb += [
            self.cfg.i.stb.eq(cfg_rtl_iface.o.stb),
            self.cfg.i.data.eq(cfg_rtl_iface.o.data),
        ]
        self.phys.append(_Phy(cfg_rtl_iface, [], []))

        for idx in range(16):
            dac = Dac()
            self.comb += dac.clear.eq(self.cfg.clr[idx]),

            for i in dac.i:
                rtl_iface = rtlink.Interface(
                    rtlink.OInterface(len(i.payload), delay=i.latency))

                self.comb += [
                    i.stb.eq(rtl_iface.o.stb),
                    i.payload.raw_bits().eq(rtl_iface.o.data),
                ]

                self.phys.append(_Phy(rtl_iface, [], []))

            setattr(self.submodules, "dac{}".format(idx), dac)

        # TODO: REMOVE
        self.submodules.logger = ShuttlerMonitor(self.dac0)
        self.phys.append(_Phy(self.logger.rtlink, [], []))
