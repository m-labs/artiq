import logging
import unittest

from migen import *

from artiq.gateware.suservo.dds_ser import DDSParams, DDS

class OutIoUpdateTB(Module):
    def __init__(self):
        self.fine_ts = Signal(3)

class TB(Module):
    def __init__(self, p):
        self.cs_n = Signal()
        self.clk = Signal()
        self.mosi = [Signal() for i in range(p.channels)]
        for i, m in enumerate(self.mosi):
            setattr(self, "mosi{}".format(i), m)
        self.miso = Signal()
        self.io_update = Signal()
        self.passthrough = Signal()

        self.io_update_phys = []
        for i in range(p.channels//4):
            phy = OutIoUpdateTB()
            self.io_update_phys.append(phy)

        clk0 = Signal()
        self.sync += clk0.eq(self.clk)
        sample = Signal()
        self.comb += sample.eq(Cat(self.clk, clk0) == 0b01)

        self.ddss = []
        for i in range(p.channels):
            dds = Record([("ftw", 32), ("pow", 16), ("asf", 16), 
                          ("cmd", 8), ("accu", 32), ("phase", 19)])
            sr = Signal(32 + 16 + 16 + 8)
            self.sync += [
                    dds.accu.eq(dds.accu + p.sysclk_per_clk * dds.ftw),
                    If(~self.cs_n & sample,
                        sr.eq(Cat(self.mosi[i], sr))
                    ),
                    If(self.io_update,
                        dds.raw_bits()[:len(sr)].eq(sr)
                    )
            ]
            self.comb += dds.phase.eq((dds.pow << 3) + (dds.accu >> 13))
            self.ddss.append(dds)

    @passive
    def log(self, data):
        i = 0
        while True:
            i += 1
            if (yield self.io_update):
                yield
                dat = []
                for dds in self.ddss:
                    v = yield from [(yield getattr(dds, k))
                            for k in "cmd ftw pow asf".split()]
                    dat.append(v)
                data.append((i, dat))
            else:
                yield


def main():
    p = DDSParams(channels=4, width=8 + 32 + 16 + 16, clk=1)
    tb = TB(p)
    dds = DDS(tb, p)
    tb.submodules += dds

    def run(tb):
        dut = dds
        for i, ch in enumerate(dut.profile):
            yield ch.eq((((0
                << 16 | i | 0x20)
                << 16 | i | 0x30)
                << 32 | i | 0x40))
        # assert (yield dut.done)
        yield dut.start.eq(1)
        yield
        yield dut.start.eq(0)
        yield
        yield
        assert not (yield dut.done)
        while not (yield dut.done):
            yield
        yield

    data = []
    run_simulation(tb, [tb.log(data), run(tb)], vcd_name="dds.vcd")

    assert data[-1][1] == [[0xe, 0x40 | i, 0x30 | i, 0x20 | i] for i in
            range(4)]


class DDSTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
