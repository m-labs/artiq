from random import Random

from artiq.language.core import delay
from artiq.language.context import AutoContext, Parameter
from artiq.language import units
from artiq.sim import time


class Core:
    def run(self, k_function, k_args, k_kwargs):
        return k_function(*k_args, **k_kwargs)


class Input(AutoContext):
    name = Parameter()
    implicit_core = False

    def build(self):
        self.prng = Random()

    def wait_edge(self):
        duration = self.prng.randrange(0, 20)*units.ms
        time.manager.event(("wait_edge", self.name, duration))
        delay(duration)

    def count_gate(self, duration):
        result = self.prng.randrange(0, 100)
        time.manager.event(("count_gate", self.name, duration, result))
        delay(duration)
        return result


class WaveOutput(AutoContext):
    name = Parameter()
    implicit_core = False

    def pulse(self, frequency, duration):
        time.manager.event(("pulse", self.name, frequency, duration))
        delay(duration)


class VoltageOutput(AutoContext):
    name = Parameter()
    implicit_core = False

    def set(self, value):
        time.manager.event(("set_voltage", self.name, value))
