import numpy as np

from migen import *
from migen.fhdl.verilog import convert

from artiq.gateware.dsp.spline import Spline
from .tools import xfer


def _test_gen_spline(dut, o):
    yield dut.o.ack.eq(1)
    yield from xfer(dut, i=dict(a0=0, a1=1, a2=2))
    for i in range(20):
        yield
        o.append((yield dut.o.a0))


def _test_spline():
    dut = Spline(order=3, width=16, step=1)

    if False:
        print(convert(dut))
    else:
        o = []
        run_simulation(dut, _test_gen_spline(dut, o), vcd_name="spline.vcd")
        o = np.array(o)
        print(o)


if __name__ == "__main__":
    _test_spline()
