import unittest
from numpy import int32, int64

import migen as mg

from artiq.coredevice import sawg
from artiq.language import delay_mu, core as core_language
from artiq.gateware.rtio.phy.sawg import Channel
from artiq.sim import devices as sim_devices, time as sim_time


class RTIOManager:
    def __init__(self):
        self.outputs = []

    def rtio_output(self, now, channel, addr, data):
        self.outputs.append((now, channel, addr, data))

    def rtio_output_list(self, *args, **kwargs):
        self.rtio_output(*args, **kwargs)

    def patch(self, mod):
        assert not hasattr(mod, "_saved")
        mod._saved = {}
        for name in "rtio_output rtio_output_list".split():
            mod._saved[name] = getattr(mod, name, None)
            setattr(mod, name, getattr(self, name))

    def unpatch(self, mod):
        mod.__dict__.update(mod._saved)
        del mod._saved


class SAWGTest(unittest.TestCase):
    def setUp(self):
        core_language.set_time_manager(sim_time.Manager())
        self.rtio_manager = RTIOManager()
        self.rtio_manager.patch(sawg)
        self.core = sim_devices.Core({})
        self.core.coarse_ref_period = 8
        self.channel = mg.ClockDomainsRenamer({"rio_phy": "sys"})(
            Channel(width=16, parallelism=2))
        self.driver = sawg.SAWG({"core": self.core}, channel_base=0,
                                parallelism=self.channel.parallelism)

    def tearDown(self):
        self.rtio_manager.unpatch(sawg)

    def test_instantiate(self):
        pass

    def test_make_events(self):
        d = self.driver
        d.offset.set(.9)
        delay_mu(2*8)
        d.frequency0.set64(.1)
        delay_mu(2*8)
        d.offset.set(0)
        self.assertEqual(
            self.rtio_manager.outputs, [
                (0, 1, 0, int(round(
                    (1 << self.driver.offset.width - 1)*.9))),
                (2*8, 8, 0, [int(round(
                    (1 << self.driver.frequency0.width) /
                    self.channel.parallelism*d.core.coarse_ref_period*.1)),
                            0]),
                (4*8, 1, 0, 0),
            ])

    def run_channel(self, events):
        def gen(dut, events):
            c = 0
            for time, channel, address, data in events:
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
                yield rt.stb.eq(1)
                assert not (yield rt.busy)

        def log(dut, data, n):
            for i in range(dut.latency):
                yield
            for i in range(n):
                yield
                data.append((yield from [(yield _) for _ in dut.o]))

        data = []
        mg.run_simulation(self.channel, [
            gen(self.channel, events),
            log(self.channel, data, int(events[-1][0]//8) + 1)],
                          vcd_name="dds.vcd")
        return sum(data, [])

    def test_run_channel(self):
        self.test_make_events()
        out = self.run_channel(self.rtio_manager.outputs)

    def test_coeff(self):
        import struct
        for v in [-.1], [.1, -.01], [.1, .01, -.00001], \
                [.1, .01, .00001, -.000000001]:
            ch = self.driver.offset
            p = ch.coeff_to_mu(v)
            t = ch.time_width
            w = ch.width
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
        d.offset.set_list_mu([100, 10])
        delay_mu(10*8)
        d.offset.set_list([0])
        delay_mu(1*8)
        out = self.run_channel(self.rtio_manager.outputs)
        for i in range(len(out)//2):
            with self.subTest(i):
                v = 100 + i*10
                self.assertEqual(out[2*i], v)
                self.assertEqual(out[2*i+1], v)

    def test_pack(self):
        ch = self.driver.offset
        self.assertEqual(ch.pack_coeff_mu([1]), [1])
        self.assertEqual(ch.pack_coeff_mu([1, 1 << 16]), [1, 1])
        self.assertEqual(ch.pack_coeff_mu([1, 1 << 32]), [1, 0])
        self.assertEqual(ch.pack_coeff_mu([0x1234, 0xa5a5a5a5]),
                         [0xa5a51234, 0xa5a5])
        self.assertEqual(ch.pack_coeff_mu([1, 2, 3, 4]),
                         [0x20001, 0x30000, 0, 4, 0])
        self.assertEqual(ch.pack_coeff_mu([-1, -2, -3, -4]),
                         [0xfffeffff, 0xfffdffff, 0xffffffff,
                          0xfffffffc, 0xffffffff])
        self.assertEqual(ch.pack_coeff_mu([0, -1, 0, -1]),
                         [0xffff0000, 0x0000ffff, 0,
                          0xffffffff, 0xffffffff])

    def test_smooth_linear(self):
        ch = self.driver.offset
        ch.smooth(.1, .2, 13*ch.core.coarse_ref_period, 1)
        ch.set(.2)
        delay_mu(1*8)
        out = self.run_channel(self.rtio_manager.outputs)
        a = int(round(.1*ch.scale))
        da = a//13
        for i in range(len(out)//2):
            with self.subTest(i):
                v = a + i*da
                self.assertEqual(out[2*i], v)
                self.assertEqual(out[2*i+1], v)

    def test_smooth_cubic(self):
        ch = self.driver.offset
        ch.smooth(.1, .2, 13*ch.core.coarse_ref_period, 3)
        ch.set(.2)
        delay_mu(1*8)
        out = self.run_channel(self.rtio_manager.outputs)
