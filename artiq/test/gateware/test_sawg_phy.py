import numpy as np
from operator import or_

from migen import *
from migen.fhdl.verilog import convert

from artiq.gateware.rtio.phy.sawg import Channel
from .tools import rtio_xfer


def pack_tri(port, *v):
    r = 0
    w = 0
    for vi, p in zip(v, port.payload.flatten()):
        w += len(p)
        r |= int(vi*(1 << w))
    return r


def gen_rtio(dut):
    yield
    yield from rtio_xfer(
        dut,
        a1=pack_tri(dut.a1.a, .1),
        f0=pack_tri(dut.b.f, .01234567),
        f1=pack_tri(dut.a1.f, .01234567),
        a2=pack_tri(dut.a1.a, .05),
        f2=pack_tri(dut.a1.f, .00534567),
    )


def gen_log(dut, o, n):
    for i in range(3 + dut.latency):
        yield
    for i in range(n):
        yield
        o.append((yield from [(yield _) for _ in dut.o]))
        #o.append([(yield dut.a1.xo[0])])


def _test_channel():
    width = 16

    dut = ClockDomainsRenamer({"rio_phy": "sys"})(
        Channel(width=width, parallelism=4)
    )

    if False:
        print(convert(dut))
        return

    o = []
    run_simulation(
        dut,
        [gen_rtio(dut), gen_log(dut, o, 128)],
        vcd_name="dds.vcd")
    o = np.array(o)/(1 << (width - 1))
    o = o.ravel()
    np.savez_compressed("dds.npz", o=o)

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2)
    ax[0].step(np.arange(o.size), o)
    ax[1].psd(o, 1 << 10, Fs=1, noverlap=1 << 9, scale_by_freq=False)
    fig.savefig("dds.pdf")
    plt.show()


if __name__ == "__main__":
    _test_channel()
