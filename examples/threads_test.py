from artiq.sim import *
from artiq.units import *

def threads_test():
	pulse("x", 1*MHz, 10*ms)
	with parallel:
		with sequential:
			wait_edge("a")
			delay(5*ms)
			pulse("a", 30*MHz, 1*us)
			wait_edge("a")
			delay(10*ms)
			pulse("a", 60*MHz, 1*us)
		with sequential:
			wait_edge("b")
			delay(3*ms)
			pulse("b", 30*MHz, 1*us)

if __name__ == "__main__":
	threads_test()
	print(time_manager.format_timeline())
