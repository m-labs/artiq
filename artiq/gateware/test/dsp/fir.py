import numpy as np
import matplotlib.pyplot as plt

from migen import *
from migen.fhdl import verilog
from artiq.gateware.dsp import fir


class Transfer(Module):
    def __init__(self, dut):
        self.submodules.dut = dut

    def drive(self, x):
        for xi in x.reshape(-1, self.dut.parallelism):
            yield [ij.eq(int(xj)) for ij, xj in zip(self.dut.i, xi)]
            yield

    def record(self, y):
        for i in range(self.dut.latency):
            yield
        for yi in y.reshape(-1, self.dut.parallelism):
            yield
            yi[:] = (yield from [(yield o) for o in self.dut.o])

    def run(self, samples, amplitude=1., seed=None):
        if seed is not None:
            np.random.seed(seed)
        w = 2**(self.dut.width - 1) - 1
        x = np.round(np.random.uniform(
            -amplitude*w, amplitude*w, samples))
        y = self.run_data(x)
        x /= w
        y /= w
        return x, y

    def run_data(self, x):
        y = np.empty_like(x)
        run_simulation(self, [self.drive(x), self.record(y)],
                       vcd_name="fir.vcd")
        return y

    def analyze(self, x, y):
        fig, ax = plt.subplots(3)
        ax[0].plot(x, "c-.", label="input")
        ax[0].plot(y, "r-", label="output")
        ax[0].legend(loc="right")
        ax[0].set_xlabel("time (1/fs)")
        ax[0].set_ylabel("signal")
        n = len(x)
        w = np.hanning(n)
        x = (x.reshape(-1, n)*w).sum(0)
        y = (y.reshape(-1, n)*w).sum(0)
        t = (np.fft.rfft(y)/np.fft.rfft(x))
        f = np.fft.rfftfreq(n)*2
        fmin = f[1]
        ax[1].plot(f,  20*np.log10(np.abs(t)), "r-")
        ax[1].set_ylim(-70, 3)
        ax[1].set_xlim(fmin, 1.)
        # ax[1].set_xscale("log")
        ax[1].set_xlabel("frequency (fs/2)")
        ax[1].set_ylabel("magnitude (dB)")
        ax[1].grid(True)
        ax[2].plot(f,  np.rad2deg(np.angle(t)), "r-")
        ax[2].set_xlim(fmin, 1.)
        # ax[2].set_xscale("log")
        ax[2].set_xlabel("frequency (fs/2)")
        ax[2].set_ylabel("phase (deg)")
        ax[2].grid(True)
        return fig


class UpTransfer(Transfer):
    def drive(self, x):
        x = x.reshape(-1, len(self.dut.o))
        x[:, 1:] = 0
        for xi in x:
            yield self.dut.i.eq(int(xi[0]))
            yield

    def record(self, y):
        for i in range(self.dut.latency):
            yield
        for yi in y.reshape(-1, len(self.dut.o)):
            yield
            yi[:] = (yield from [(yield o) for o in self.dut.o])


def _main():
    if True:
        coeff = fir.halfgen4_cascade(2, width=.4, order=8)
        dut = fir.ParallelHBFUpsampler(coeff, width=16)
        # print(verilog.convert(dut, ios=set([dut.i] + dut.o)))
        tb = UpTransfer(dut)
    else:
        coeff = fir.halfgen4(.4/2, 8)
        dut = fir.ParallelFIR(coeff, parallelism=4, width=16)
        # print(verilog.convert(dut, ios=set(dut.i + dut.o)))
        tb = Transfer(dut)

    if True:
        x, y = tb.run(samples=1 << 10, amplitude=.5, seed=0x1234567)
    else:
        x = np.zeros(100)
        x[:50] = 1 << 8
        x[50:] = 1 << 13
        y = tb.run_data(x)
    tb.analyze(x, y)
    plt.show()


if __name__ == "__main__":
    _main()
