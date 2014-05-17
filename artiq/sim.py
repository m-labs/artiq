from random import Random
from operator import itemgetter

from artiq import units

class SequentialTimeContext:
	def __init__(self, current_time):
		self.current_time = current_time
		self.block_duration = 0

	def take_time(self, amount):
		self.current_time += amount
		self.block_duration += amount

class ParallelTimeContext:
	def __init__(self, current_time):
		self.current_time = current_time
		self.block_duration = 0

	def take_time(self, amount):
		if amount > self.block_duration:
			self.block_duration = amount	

class TimeManager:
	def __init__(self):
		self.stack = [SequentialTimeContext(0)]
		self.timeline = []

	def enter_sequential(self):
		new_context = SequentialTimeContext(self.stack[-1].current_time)
		self.stack.append(new_context)

	def enter_parallel(self):
		new_context = ParallelTimeContext(self.stack[-1].current_time)
		self.stack.append(new_context)

	def exit(self):
		old_context = self.stack.pop()
		self.take_time(old_context.block_duration)

	def take_time(self, amount):
		self.stack[-1].take_time(amount)

	def event(self, description):
		self.timeline.append((self.stack[-1].current_time, description))

	def format_timeline(self):
		r = ""
		prev_time = 0
		for time, description in sorted(self.timeline, key=itemgetter(0)):
			t = units.Quantity(time, units.base_s_unit)
			dt = units.Quantity(time-prev_time, units.base_s_unit)
			r += "@{:10} (+{:10}) ".format(str(t), str(dt))
			for item in description:
				r += "{:16}".format(str(item))
			r += "\n"
			prev_time = time
		return r

# global namespace for interpreted kernels

time_manager = TimeManager()
prng = Random(42)

class _Sequential:
	def __enter__(self):
		time_manager.enter_sequential()

	def __exit__(self, type, value, traceback):
		time_manager.exit()
sequential = _Sequential()

class _Parallel:
	def __enter__(self):
		time_manager.enter_parallel()

	def __exit__(self, type, value, traceback):
		time_manager.exit()
parallel = _Parallel()

def delay(duration):
	units.check_unit(duration, units.base_s_unit)
	time_manager.take_time(duration.amount)

def wait_edge(input):
	duration = prng.randrange(17)*units.ms
	time_manager.event(("wait_edge", input, duration))
	time_manager.take_time(duration.amount)

def pulse(output, frequency, duration):
	units.check_unit(frequency, units.base_Hz_unit)
	units.check_unit(duration, units.base_s_unit)
	time_manager.event(("pulse", output, frequency, duration))
	time_manager.take_time(duration.amount)

def count_gate(input, duration):
	result = prng.randrange(100)
	units.check_unit(duration, units.base_s_unit)
	time_manager.event(("count_gate", input, duration, result))
	time_manager.take_time(duration.amount)
	return result

def set_dac_voltage(output):
	time_manager.event(("set_dac_voltage", output))
