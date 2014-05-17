from artiq.sim import *
from artiq.units import *

def al_clock_probe(spectroscopy_freq, A1, A2):
	state_0_count = 0
	for count in range(100):
		wait_edge("mains_sync")
		pulse("laser_cooling", 100*MHz, 100*us)
		delay(5*us)
		with parallel:
			pulse("spectroscopy", spectroscopy_freq, 100*us)
			with sequential:
				delay(50*us)
				set_dac_voltage("spectroscopy_b")
		delay(5*us)
		while True:
			delay(5*us)
			with parallel:
				pulse("state_detection", 100*MHz, 10*us)
				photon_count = count_gate("pmt", 10*us)
			if photon_count < A1 or photon_count > A2:
				break
		if photon_count < A1:
			state_0_count += 1
	return state_0_count 

if __name__ == "__main__":
	al_clock_probe(30*MHz, 3, 30)
	print(time_manager.format_timeline())
