import unittest

import migen as mg
from numpy import int32

from artiq.coredevice import sawg, spline
from artiq.language import (at_mu, now_mu, delay,
                            core as core_language)
from artiq.gateware.rtio.phy.sawg import Channel
from artiq.sim import devices as sim_devices, time as sim_time


class RTIOManager:
    def __init__(self):
        self.outputs = []

    def rtio_output(self, target, data):
        channel = target >> 8
        addr = target & 0xff
        self.outputs.append((now_mu(), channel, addr, data))

    def rtio_output_wide(self, *args, **kwargs):
        self.rtio_output(*args, **kwargs)

    def delay_mu(self, t):
        delay(t)

    def patch(self, mod):
        assert not hasattr(mod, "_saved")
        mod._saved = {}
        for name in "rtio_output rtio_output_wide delay_mu".split():
            mod._saved[name] = getattr(mod, name, None)
            setattr(mod, name, getattr(self, name))

    def unpatch(self, mod):
        mod.__dict__.update(mod._saved)
        del mod._saved


class SAWGTest(unittest.TestCase):
    def setUp(self):
        core_language.set_time_manager(sim_time.Manager())
        self.rtio_manager = RTIOManager()
        self.rtio_manager.patch(spline)
        self.rtio_manager.patch(sawg)
        self.core = sim_devices.Core({})
        self.core.coarse_ref_period = 20/3
        self.core.ref_multiplier = 1
        self.t = self.core.coarse_ref_period
        self.channel = mg.ClockDomainsRenamer({"rio_phy": "sys"})(
            Channel(width=16, parallelism=2))
        self.driver = sawg.SAWG({"core": self.core}, channel_base=0,
                                parallelism=self.channel.parallelism)

    def tearDown(self):
        self.rtio_manager.unpatch(spline)
        self.rtio_manager.unpatch(sawg)

    def test_instantiate(self):
        pass

    def test_make_events(self):
        d = self.driver
        d.offset.set(.9)
        delay(2*self.t)
        d.frequency0.set(.1)
        d.frequency1.set(.1)
        delay(2*self.t)
        d.offset.set(0)
        v = int(round((1 << 48) * .1 * self.t))
        self.assertEqual(
            self.rtio_manager.outputs, [
                (0., 1, 0, int(round(self.driver.offset.scale*.9))),
                (2.*self.t, 8, 0, int(round(
                    (1 << self.driver.frequency0.width) *
                    self.t/self.channel.parallelism*.1))),
                (2.*self.t, 3, 0, [int32(v), int32(v >> 32)]),
                (4.*self.t, 1, 0, 0),
            ])

    def run_channel(self, events):
        def gen(dut, events):
            c = 0
            for time, channel, address, data in events:
                time //= self.t
                assert c <= time
                while c < time:
                    yield
                    c += 1
                    for phy in dut.phys:
                        yield phy.rtlink.o.stb.eq(0)
                rt = dut.phys[channel].rtlink.o
                if isinstance(data, list):
                    data = sum(int(d) << (i*32) for i, d in enumerate(data))
                yield rt.data.eq(int(data))
                if hasattr(rt, "address"):
                    yield rt.address.eq(address)
                yield rt.stb.eq(1)
                assert not (yield rt.busy)
                # print("{}: set ch {} to {}".format(time, channel, hex(data)))

        def log(dut, data, n):
            for i in range(n + dut.latency):
                yield
                data.append((yield from [(yield _) for _ in dut.o]))

        data = []
        # print(int(events[-1][0]) + 1)
        mg.run_simulation(self.channel, [
            gen(self.channel, events),
            log(self.channel, data, int(events[-1][0]//self.t) + 1)],
                          vcd_name="dds.vcd")
        return data

    def test_run_channel(self):
        self.test_make_events()
        self.run_channel(self.rtio_manager.outputs)

    def test_coeff(self):
        import struct
        # these get discrete_compensate
        # [.1, .01, -.00001], [.1, .01, .00001, -.000000001]
        for v in [-.1], [.1, -.01]:
            ch = self.driver.offset
            p = ch.coeff_as_packed(v)
            t = ch.time_width
            w = ch.width
            p = [_ & 0xffffffff for _ in p]
            p0 = [int(round(vi*ch.scale*ch.time_scale**i))
                  for i, vi in enumerate(v)]
            p0 = [struct.pack("<" + "_bhiiqqqq"[(w + i*t)//8], vi
                              )[:(w + i*t)//8]
                  for i, vi in enumerate(p0)]
            p0 = b"".join(p0)
            if len(p0) % 4:
                p0 += b"\x00"*(4 - len(p0) % 4)
            p0 = list(struct.unpack("<" + "I"*((len(p0) + 3)//4), p0))
            with self.subTest(v):
                self.assertEqual(p, p0)

    def test_linear(self):
        d = self.driver
        d.offset.set_coeff_mu([100, 10])
        delay(10*self.t)
        d.offset.set_coeff([0])
        delay(1*self.t)
        out = self.run_channel(self.rtio_manager.outputs)
        out = out[self.channel.latency + self.channel.u.latency:][:11]
        for i in range(len(out) - 1):
            with self.subTest(i):
                v = 100 + i*10
                self.assertEqual(out[i], [v, v])
        self.assertEqual(out[-1], [0, 0])

    def test_pack(self):
        ch = self.driver.offset
        self.assertEqual(ch.coeff_as_packed_mu([1]), [1])
        self.assertEqual(ch.coeff_as_packed_mu([1, 1 << 16]), [1, 1])
        self.assertEqual(ch.coeff_as_packed_mu([1, 1 << 32]), [1, 0])
        self.assertEqual(ch.coeff_as_packed_mu([0x1234, 0xa5a5a5a5]),
                         [0xa5a51234, 0xa5a5])
        self.assertEqual(ch.coeff_as_packed_mu([1, 2, 3, 4]),
                         [0x20001, 0x30000, 0, 4, 0])
        self.assertEqual(ch.coeff_as_packed_mu([-1, -2, -3, -4]),
                         [0xfffeffff, 0xfffdffff, -1, -4, -1])
        self.assertEqual(ch.coeff_as_packed_mu([0, -1, 0, -1]),
                         [0xffff0000, 0x0000ffff, 0, -1, -1])

    def test_smooth_linear(self):
        ch = self.driver.offset
        ch.smooth(.1, .2, 13*self.t, 1)
        ch.set(.2)
        delay(1*self.t)
        out = self.run_channel(self.rtio_manager.outputs)
        out = out[self.channel.latency + self.channel.u.latency:][:14]
        a = int(round(.1*ch.scale))
        da = int(round(.1*ch.scale*(1 << ch.width)//13))
        for i in range(len(out) - 1):
            with self.subTest(i):
                v = a + (i*da >> ch.width)
                self.assertEqual(out[i], [v, v])
        a = int(round(.2*ch.scale))
        self.assertEqual(out[-1], [a, a])

    def test_smooth_cubic(self):
        ch = self.driver.offset
        ch.smooth(.1, .2, 13*self.t, 3)
        ch.set(.2)
        delay(1*self.t)
        out = self.run_channel(self.rtio_manager.outputs)
        out = out[self.channel.latency + self.channel.u.latency:][:14]
        if False:
            import matplotlib.pyplot as plt
            plt.plot(sum(out, []))
            plt.show()

    @unittest.skip("needs artiq.sim.time.TimeManager tweak for "
                   "reverse timeline jumps")
    def test_demo_2tone(self):
        MHz = 1e-3
        ns = 1.
        self.sawg0 = self.driver

        t_up = t_hold = t_down = 400*ns
        a1 = .3
        a2 = .4
        order = 3

        self.sawg0.frequency0.set(10*MHz)
        self.sawg0.phase0.set(0.)
        self.sawg0.frequency1.set(1*MHz)
        self.sawg0.phase1.set(0.)
        self.sawg0.frequency2.set(13*MHz)
        self.sawg0.phase2.set(0.)
        t = now_mu()
        self.sawg0.amplitude1.smooth(.0, a1, t_up, order)
        at_mu(t)
        self.sawg0.amplitude2.smooth(.0, a2, t_up, order)
        self.sawg0.amplitude1.set(a1)
        self.sawg0.amplitude2.set(a2)
        delay(t_hold)
        t = now_mu()
        self.sawg0.amplitude1.smooth(a1, .0, t_down, order)
        at_mu(t)
        self.sawg0.amplitude2.smooth(a2, .0, t_down, order)
        self.sawg0.amplitude1.set(.0)
        self.sawg0.amplitude2.set(.0)

        out = self.run_channel(self.rtio_manager.outputs)
        out = sum(out, [])
        if True:
            import matplotlib.pyplot as plt
            plt.plot(out)
            plt.show()

    def test_fir_overflow(self):
        MHz = 1e-3
        ns = 1.
        f1 = self.driver.frequency1
        a1 = self.driver.amplitude1
        p1 = self.driver.phase1
        cfg = self.driver.config
        f1.set(1*MHz)
        a1.set(.99)
        delay(100*ns)
        p1.set(.5)
        delay(100*ns)
        a1.set(0)

        out = self.run_channel(self.rtio_manager.outputs)
        out = sum(out, [])
        if False:
            import matplotlib.pyplot as plt
            plt.plot(out)
            plt.show()
