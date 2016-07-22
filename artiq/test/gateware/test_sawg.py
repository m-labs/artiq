import numpy as np

from migen import *
from migen.fhdl.verilog import convert

from artiq.gateware.dsp.sawg import DDSFast
from artiq.gateware.dsp.tools import xfer


def _test_gen_dds(dut, o):
    yield from xfer(dut,
                    a=dict(a=10),
                    p=dict(p=0),
                    f=dict(f=1 << 8),
                    )
    for i in range(256//dut.parallelism):
        yield
        o.append((yield from [(yield _) for _ in dut.o]))


def _test_channel():
    dut = DDSFast(width=8, parallelism=2)

    if False:
        print(convert(dut))
    else:
        o = []
        run_simulation(dut, _test_gen_dds(dut, o), vcd_name="dds.vcd")
        o = np.array(o)
        print(o[:, :])


if __name__ == "__main__":
    _test_channel()
