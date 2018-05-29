import sys
import select

from artiq.experiment import *


def chunker(seq, size):
    res = []
    for el in seq:
        res.append(el)
        if len(res) == size:
            yield res
            res = []
    if res:
        yield res


def is_enter_pressed() -> TBool:
    if select.select([sys.stdin,], [], [], 0.0)[0]:
        sys.stdin.read(1)
        return True
    else:
        return False


class KasliTester(EnvExperiment):
    def build(self):
        # hack to detect artiq_run
        if self.get_device("scheduler").__class__.__name__ != "DummyScheduler":
            raise NotImplementedError(
                "must be run with artiq_run to support keyboard interaction")

        self.setattr_device("core")

        self.leds = dict()
        self.ttl_outs = dict()
        self.ttl_ins = dict()
        self.urukul_cplds = dict()
        self.urukuls = dict()
        self.samplers = dict()
        self.zotinos = dict()

        ddb = self.get_device_db()
        for name, desc in ddb.items():
            if isinstance(desc, dict) and desc["type"] == "local":
                module, cls = desc["module"], desc["class"]
                if (module, cls) == ("artiq.coredevice.ttl", "TTLOut"):
                    dev = self.get_device(name)
                    if "led" in name:  # guess
                        self.leds[name] = dev
                    else:
                        self.ttl_outs[name] = dev
                elif (module, cls) == ("artiq.coredevice.ttl", "TTLInOut"):
                    self.ttl_ins[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.urukul", "CPLD"):
                    self.urukul_cplds[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.ad9910", "AD9910"):
                    self.urukuls[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.sampler", "Sampler"):
                    self.samplers[name] = self.get_device(name)
                elif (module, cls) == ("artiq.coredevice.zotino", "Zotino"):
                    self.zotinos[name] = self.get_device(name)

        # Remove Urukul, Sampler and Zotino control signals
        # from TTL outs (tested separately)
        ddb = self.get_device_db()
        for name, desc in ddb.items():
            if isinstance(desc, dict) and desc["type"] == "local":
                module, cls = desc["module"], desc["class"]
                if ((module, cls) == ("artiq.coredevice.ad9910", "AD9910")
                    or (module, cls) == ("artiq.coredevice.ad9912", "AD9912")):
                    sw_device = desc["arguments"]["sw_device"]
                    del self.ttl_outs[sw_device]
                elif (module, cls) == ("artiq.coredevice.urukul", "CPLD"):
                    io_update_device = desc["arguments"]["io_update_device"]
                    del self.ttl_outs[io_update_device]
                elif (module, cls) == ("artiq.coredevice.sampler", "Sampler"):
                    cnv_device = desc["arguments"]["cnv_device"]
                    del self.ttl_outs[cnv_device]
                elif (module, cls) == ("artiq.coredevice.zotino", "Zotino"):
                    ldac_device = desc["arguments"]["ldac_device"]
                    clr_device = desc["arguments"]["clr_device"]
                    del self.ttl_outs[ldac_device]
                    del self.ttl_outs[clr_device]

        # Sort everything by RTIO channel number
        self.leds = sorted(self.leds.items(), key=lambda x: x[1].channel)
        self.ttl_outs = sorted(self.ttl_outs.items(), key=lambda x: x[1].channel)
        self.ttl_ins = sorted(self.ttl_ins.items(), key=lambda x: x[1].channel)
        self.urukuls = sorted(self.urukuls.items(), key=lambda x: x[1].sw.channel)
        self.samplers = sorted(self.samplers.items(), key=lambda x: x[1].cnv.channel)
        self.zotinos = sorted(self.zotinos.items(), key=lambda x: x[1].bus.channel)

    @kernel
    def test_led(self, led):
        while not is_enter_pressed():
            self.core.break_realtime()
            # do not fill the FIFOs too much to avoid long response times
            t = now_mu() - self.core.seconds_to_mu(0.2)
            while self.core.get_rtio_counter_mu() < t:
                pass
            for i in range(3):
                led.pulse(100*ms)
                delay(100*ms)

    def test_leds(self):
        print("*** Testing LEDs.")
        print("Check for blinking. Press ENTER when done.")

        for led_name, led_dev in self.leds:
            print("Testing LED: {}".format(led_name))
            self.test_led(led_dev)

    @kernel
    def test_ttl_out_chunk(self, ttl_chunk):
        while not is_enter_pressed():
            self.core.break_realtime()
            for _ in range(50000):
                i = 0
                for ttl in ttl_chunk:
                    i += 1
                    for _ in range(i):
                        ttl.pulse(1*us)
                        delay(1*us)
                    delay(10*us)

    def test_ttl_outs(self):
        print("*** Testing TTL outputs.")
        print("Outputs are tested in groups of 4. Touch each TTL connector")
        print("with the oscilloscope probe tip, and check that the number of")
        print("pulses corresponds to its number in the group.")
        print("Press ENTER when done.")

        for ttl_chunk in chunker(self.ttl_outs, 4):
            print("Testing TTL outputs: {}.".format(", ".join(name for name, dev in ttl_chunk)))
            self.test_ttl_out_chunk([dev for name, dev in ttl_chunk])

    @kernel
    def test_ttl_in(self, ttl_out, ttl_in):
        n = 42
        self.core.break_realtime()
        with parallel:
            ttl_in.gate_rising(1*ms)
            with sequential:
                delay(50*us)
                for _ in range(n):
                    ttl_out.pulse(2*us)
                    delay(2*us)
        return ttl_in.count() == n

    def test_ttl_ins(self):
        print("*** Testing TTL inputs.")

        ttl_out_name, ttl_out_dev = next(iter(self.ttl_outs))
        for ttl_in_name, ttl_in_dev in self.ttl_ins:
            print("Connect {} to {}. Press ENTER when done."
                  .format(ttl_out_name, ttl_in_name))
            input()
            if self.test_ttl_in(ttl_out_dev, ttl_in_dev):
                print("PASSED")
            else:
                print("FAILED")

    @kernel
    def init_urukul(self, cpld):
        self.core.break_realtime()
        cpld.init()

    @kernel
    def setup_urukul(self, channel, frequency):
        self.core.break_realtime()
        channel.init()
        channel.set(frequency*MHz)
        channel.sw.on()
        channel.set_att(6.)

    @kernel
    def rf_switch_wave(self, channels):
        while not is_enter_pressed():
            self.core.break_realtime()
            # do not fill the FIFOs too much to avoid long response times
            t = now_mu() - self.core.seconds_to_mu(0.2)
            while self.core.get_rtio_counter_mu() < t:
                pass
            for channel in channels:
                channel.sw.pulse(100*ms)
                delay(100*ms)

    # We assume that RTIO channels for switches are grouped by card.
    def test_urukuls(self):
        print("*** Testing Urukul DDSes.")

        print("Initializing CPLDs...")
        for name, cpld in sorted(self.urukul_cplds.items(), key=lambda x: x[0]):
            print(name + "...")
            self.init_urukul(cpld)
        print("...done")

        print("Frequencies:")
        for card_n, channels in enumerate(chunker(self.urukuls, 4)):
            for channel_n, (channel_name, channel_dev) in enumerate(channels):
                frequency = 10*(card_n + 1) + channel_n
                print("{}\t{}MHz".format(channel_name, frequency))
                self.setup_urukul(channel_dev, frequency)
        print("Press ENTER when done.")
        input()

        print("Testing RF switch control. Press ENTER when done.")
        self.rf_switch_wave([channel_dev for channel_name, channel_dev in self.urukuls])

    @kernel
    def get_sampler_voltages(self, sampler, cb):
        self.core.break_realtime()
        sampler.init()
        delay(5*ms)
        for i in range(8):
            sampler.set_gain_mu(i, 0)
            delay(100*us)
        smp = [0.0]*8
        sampler.sample(smp)
        cb(smp)

    def test_samplers(self):
        print("*** Testing Sampler ADCs.")
        for card_name, card_dev in self.samplers:
            print("Testing: ", card_name)

            for channel in range(8):
                print("Apply 1.5V to channel {}. Press ENTER when done.".format(channel))
                input()

                voltages = []
                def setv(x):
                    nonlocal voltages
                    voltages = x
                self.get_sampler_voltages(card_dev, setv)

                passed = True
                for n, voltage in enumerate(voltages):
                    if n == channel:
                        if abs(voltage - 1.5) > 0.2:
                            passed = False
                    else:
                        if abs(voltage) > 0.2:
                            passed = False
                if passed:
                    print("PASSED")
                else:
                    print("FAILED")
                    print(" ".join(["{:.1f}".format(x) for x in voltages]))

    @kernel
    def set_zotino_voltages(self, zotino, voltages):
        self.core.break_realtime()
        zotino.init()
        delay(100*us)
        i = 0
        for voltage in voltages:
            zotino.write_dac(i, voltage)
            delay(100*us)
            i += 1
        zotino.load()

    def test_zotinos(self):
        print("*** Testing Zotino DACs.")
        print("Voltages:")
        for card_n, (card_name, card_dev) in enumerate(self.zotinos):
            voltages = [2*card_n + (-1)**i*0.1*(i//2+1) for i in range(32)]
            print(card_name, " ".join(["{:.1f}".format(x) for x in voltages]))
            self.set_zotino_voltages(card_dev, voltages)
        print("Press ENTER when done.")
        input()

    def run(self):
        print("****** Kasli system tester ******")
        print("")
        self.core.reset()
        self.test_leds()
        self.test_ttl_outs()
        self.test_ttl_ins()
        self.test_urukuls()
        self.test_samplers()
        self.test_zotinos()
