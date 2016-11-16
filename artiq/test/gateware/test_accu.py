import numpy as np

from migen import *
from migen.fhdl.verilog import convert

from artiq.gateware.dsp.accu import Accu, PhasedAccu
from .tools import xfer


def read(o, n):
    p = []
    for i in range(n):
        p.append((yield from [(yield pi) for pi in o.payload.flatten()]))
        yield
    return p


def _test_gen_accu(dut, o):
    yield dut.o.ack.eq(1)
    yield from xfer(dut, i=dict(p=0, f=1, clr=1))
    o.extend((yield from read(dut.o, 8)))
    yield from xfer(dut, i=dict(p=0, f=2, clr=0))
    o.extend((yield from read(dut.o, 8)))
    yield from xfer(dut, i=dict(p=0, f=2, clr=1))
    o.extend((yield from read(dut.o, 8)))
    yield from xfer(dut, i=dict(p=8, f=-1, clr=1))
    o.extend((yield from read(dut.o, 8)))
    yield from xfer(dut, i=dict(p=0, f=0, clr=1))
    yield from xfer(dut, i=dict(p=1, f=0, clr=0))
    o.extend((yield from read(dut.o, 8)))


def _test_accu():
    dut = PhasedAccu(8, parallelism=8)

    if False:
        print(convert(dut))
    else:
        o = []
        run_simulation(dut, _test_gen_accu(dut, o), vcd_name="accu.vcd")
        o = np.array(o)
        print(o)


if __name__ == "__main__":
    _test_accu()
