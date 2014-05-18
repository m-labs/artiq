from random import Random
from collections import namedtuple

Pulse = namedtuple("Pulse", "time output frequency duration")
WaitEdge = namedtuple("WaitEdge", "time input")

class Parallel:
	def __init__(self, *threads):
		self.threads = threads

def threads_test(now):
	yield Pulse(now, "x", 1, 10)
	now += 10

	def thread0(now):
		now = yield WaitEdge(now, "a")
		now += 5
		yield Pulse(now, "a", 30, 1)
		now += 1
		now = yield WaitEdge(now, "a")
		now += 10
		yield Pulse(now, "a", 60, 1)
		now += 1
		return now

	def thread1(now):
		now = yield WaitEdge(now, "b")
		now += 3
		yield Pulse(now, "b", 30, 1)
		now += 1
		return now

	now = yield Parallel(thread0(now), thread1(now))

	return now

prng = Random(42)

def execute(threads):
	end_time = 0
	thread_replies = [None]*len(threads)
	continue_execute = True

	while continue_execute:
		continue_execute = False
		new_thread_replies = []
		for thread, send_data in zip(threads, thread_replies):
			try:
				thread_request = thread.send(send_data)
			except StopIteration as e:
				if e.value > end_time:
					end_time = e.value
			else:
				continue_execute = True
				thread_reply = None
				if isinstance(thread_request, Pulse):
					yield thread_request
				elif isinstance(thread_request, WaitEdge):
					yield thread_request
					edge_delay = prng.randrange(100)
					print("*** Simulating input edge on '{}' after {}".format(thread_request.input, edge_delay))
					thread_reply = thread_request.time + edge_delay
				elif isinstance(thread_request, Parallel):
					thread_reply = yield from execute(thread_request.threads)
				else:
					raise TypeError
				new_thread_replies.append(thread_reply)
		thread_replies = new_thread_replies

	return end_time

if __name__ == "__main__":
	ex = execute([threads_test(0)])
	while True:
		try:
			ev = next(ex)
		except StopIteration as e:
			print("*** Execution ended at {}".format(e.value))
			break
		else:
			print(ev)
