from operator import itemgetter

from artiq.language.units import *
from artiq.language import core as core_language


class SequentialTimeContext:
    def __init__(self, current_time):
        self.current_time = current_time
        self.block_duration = 0*s

    def take_time(self, amount):
        self.current_time += amount
        self.block_duration += amount


class ParallelTimeContext:
    def __init__(self, current_time):
        self.current_time = current_time
        self.block_duration = 0*s

    def take_time(self, amount):
        if amount > self.block_duration:
            self.block_duration = amount


class Manager:
    def __init__(self):
        self.stack = [SequentialTimeContext(0*s)]
        self.timeline = []

    def enter_sequential(self):
        new_context = SequentialTimeContext(self.get_time_mu())
        self.stack.append(new_context)

    def enter_parallel(self):
        new_context = ParallelTimeContext(self.get_time_mu())
        self.stack.append(new_context)

    def exit(self):
        old_context = self.stack.pop()
        self.take_time(old_context.block_duration)

    def take_time_mu(self, duration):
        self.stack[-1].take_time(duration)

    def get_time_mu(self):
        return self.stack[-1].current_time

    def set_time_mu(self, t):
        dt = t - self.get_time_mu()
        if dt < 0*s:
            raise ValueError("Attempted to go back in time")
        self.take_time(dt)

    take_time = take_time_mu

    def event(self, description):
        self.timeline.append((self.get_time_mu(), description))

    def format_timeline(self):
        r = ""
        prev_time = 0*s
        for time, description in sorted(self.timeline, key=itemgetter(0)):
            r += "@{:.9f} (+{:.9f}) ".format(time, time-prev_time)
            for item in description:
                r += "{:16}".format(str(item))
            r += "\n"
            prev_time = time
        return r

manager = Manager()
core_language.set_time_manager(manager)
