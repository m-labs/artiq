from random import Random

from artiq.language import units
from artiq.sim import time

class Core:
	def run(self, k_function, *k_args, **k_kwargs):
		return k_function(*k_args, **k_kwargs)

class Input:
	def __init__(self, name, prng_seed=None, wait_max=20, count_max=100, wait_min=0, count_min=0):
		self.name = name
		self.wait_min = wait_min
		self.wait_max = wait_max
		self.count_min = count_min
		self.count_max = count_max
		self.prng = Random(prng_seed)

	def wait_edge(self):
		duration = self.prng.randrange(self.wait_min, self.wait_max)*units.ms
		time.manager.event(("wait_edge", self.name, duration))
		time.manager.take_time(duration.amount)

	def count_gate(self, duration):
		result = self.prng.randrange(self.count_min, self.count_max)
		units.check_unit(duration, units.base_s_unit)
		time.manager.event(("count_gate", self.name, duration, result))
		time.manager.take_time(duration.amount)
		return result

class WaveOutput:
	def __init__(self, name):
		self.name = name

	def pulse(self, frequency, duration):
		units.check_unit(frequency, units.base_Hz_unit)
		units.check_unit(duration, units.base_s_unit)
		time.manager.event(("pulse", self.name, frequency, duration))
		time.manager.take_time(duration.amount)

class VoltageOutput:
	def __init__(self, name):
		self.name = name

	def set(self, value):
		time.manager.event(("set_voltage", self.name, value))
