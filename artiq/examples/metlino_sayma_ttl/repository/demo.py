import sys
import os
import select

from artiq.experiment import *
from artiq.coredevice.fmcdio_vhdci_eem import *


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
    if os.name == "nt":
        if msvcrt.kbhit() and msvcrt.getch() == b"\r":
            return True
        else:
            return False
    else:
        if select.select([sys.stdin, ], [], [], 0.0)[0]:
            sys.stdin.read(1)
            return True
        else:
            return False


class Demo(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.setattr_device("fmcdio_dirctl")

        self.leds = dict()
        self.ttl_outs = dict()

        ddb = self.get_device_db()
        for name, desc in ddb.items():
            if isinstance(desc, dict) and desc["type"] == "local":
                module, cls = desc["module"], desc["class"]
                if (module, cls) == ("artiq.coredevice.ttl", "TTLOut"):
                    dev = self.get_device(name)
                    if "led" in name:   # guess
                        self.leds[name] = dev
                    elif "ttl" in name: # to exclude fmcdio_dirctl
                        self.ttl_outs[name] = dev

        self.leds = sorted(self.leds.items(), key=lambda x: x[1].channel)
        self.ttl_outs = sorted(self.ttl_outs.items(), key=lambda x: x[1].channel)

        self.dirctl_word = (
            shiftreg_bits(0, dio_bank0_out_pins | dio_bank1_out_pins) |
            shiftreg_bits(1, dio_bank0_out_pins | dio_bank1_out_pins)
        )

    @kernel
    def init(self):
        self.core.break_realtime()
        print("*** Waiting for DRTIO ready...")
        drtio_indices = [7]
        for i in drtio_indices:
            while not self.drtio_is_up(i):
                pass

        self.fmcdio_dirctl.set(self.dirctl_word)

    @kernel
    def drtio_is_up(self, drtio_index):
        if not self.core.get_rtio_destination_status(drtio_index):
            return False
        print("DRTIO #", drtio_index, "is ready\n")
        return True

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

    def run(self):
        self.core.reset()

        if self.leds:
            self.test_leds()
        if self.ttl_outs:
            self.test_ttl_outs()
