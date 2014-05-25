def collapse_test():
	for i in range(3):
		with parallel:
			with sequential:
				pulse("a", 100*MHz, 10*us)
				delay(10*us)
				pulse("b", 100*MHz, 10*us)
				delay(20*us)
			with sequential:
				pulse("a", 100*MHz, 10*us)
				delay(10*us)
				pulse("b", 100*MHz, 10*us)
				delay(10*us)
