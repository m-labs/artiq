from random import Random

from artiq.language.core import delay, kernel
from artiq.language.db import AutoDB, Argument
from artiq.language import units
from artiq.sim import time


class Core(AutoDB):
    class DBKeys:
        implicit_core = False

    _level = 0

    def run(self, k_function, k_args, k_kwargs):
        Core._level += 1
        r = k_function(*k_args, **k_kwargs)
        Core._level -= 1
        if Core._level == 0:
            print(time.manager.format_timeline())
        return r


class Input(AutoDB):
    class DBKeys:
        name = Argument()

    def build(self):
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


class WaveOutput(AutoDB):
    class DBKeys:
        name = Argument()

    @kernel
    def pulse(self, frequency, duration):
        time.manager.event(("pulse", self.name, frequency, duration))
        delay(duration)


class VoltageOutput(AutoDB):
    class DBKeys:
        name = Argument()

    @kernel
    def set(self, value):
        time.manager.event(("set_voltage", self.name, value))
