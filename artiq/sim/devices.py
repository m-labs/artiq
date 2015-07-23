from random import Random

from artiq.language.core import delay, kernel
from artiq.language import units
from artiq.sim import time


class Core:
    def __init__(self, dmgr):
        self.ref_period = 1
        self._level = 0

    def run(self, k_function, k_args, k_kwargs):
        self._level += 1
        r = k_function(*k_args, **k_kwargs)
        self._level -= 1
        if self._level == 0:
            print(time.manager.format_timeline())
        return r


class Input:
    def __init__(self, dmgr, name):
        self.core = dmgr.get("core")
        self.name = name

        self.prng = Random()

    @kernel
    def wait_edge(self):
        duration = self.prng.randrange(0, 20)*units.ms
        time.manager.event(("wait_edge", self.name, duration))
        delay(duration)

    @kernel
    def count_gate(self, duration):
        result = self.prng.randrange(0, 100)
        time.manager.event(("count_gate", self.name, duration, result))
        delay(duration)
        return result


class WaveOutput:
    def __init__(self, dmgr, name):
        self.core = dmgr.get("core")
        self.name = name

    @kernel
    def pulse(self, frequency, duration):
        time.manager.event(("pulse", self.name, frequency, duration))
        delay(duration)


class VoltageOutput:
    def __init__(self, dmgr, name):
        self.core = dmgr.get("core")
        self.name = name

    @kernel
    def set(self, value):
        time.manager.event(("set_voltage", self.name, value))
