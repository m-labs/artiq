from operator import itemgetter

from artiq.language import units, experiment

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

class Manager:
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

	def take_time(self, duration):
		self.stack[-1].take_time(duration)

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

manager = Manager()
experiment.set_time_manager(manager)
