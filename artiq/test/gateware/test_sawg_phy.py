import numpy as np

from migen import *
from migen.fhdl.verilog import convert

from artiq.gateware.rtio.phy.sawg import Channel
from artiq.gateware.dsp.tools import xfer, szip


def rtio_xfer(dut, **kwargs):
    yield from szip(*(
        xfer(dut.phys_names[k].rtlink, o={"data": v})
        for k, v in kwargs.items()))


def gen_rtio(dut):
    width = dut.width
    yield
    yield from rtio_xfer(
        dut, a=int(.1 * (1 << width)),
        f=int(.01234567 * (1 << 2*width)),
        p=0)


def gen_log(dut, o, n):
    for i in range(3 + dut.latency):
        yield
    for i in range(n):
        yield
        o.append((yield from [(yield _) for _ in dut.o]))


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
        [gen_rtio(dut), gen_log(dut, o, 256 * 2)],
    )  # vcd_name="dds.vcd")
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
