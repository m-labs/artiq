import numpy as np

from migen import *
from migen.fhdl.verilog import convert

from artiq.gateware.dsp import sawg
from artiq.gateware.test.dsp.tools import xfer


def _test_gen_dds(dut, o):
    yield from xfer(dut,
                    a=dict(a0=10),
                    p=dict(a0=0),
                    f=dict(a0=1),
                    )
    for i in range(256//dut.parallelism):
        yield
        o.append((yield from [(yield _) for _ in dut.xo]))


def _test_channel():
    widths = sawg._Widths(t=8, a=4*8, p=8, f=16)
    orders = sawg._Orders(a=4, p=1, f=2)
    dut = sawg.SplineParallelDDS(widths, orders, parallelism=2)

    if False:
        print(convert(dut))
    else:
        o = []
        run_simulation(dut, _test_gen_dds(dut, o), vcd_name="dds.vcd")
        o = np.array(o)
        print(o[:, :])


if __name__ == "__main__":
    _test_channel()
