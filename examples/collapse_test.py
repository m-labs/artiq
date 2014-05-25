def collapse_test():
	for i in range(3):
		with parallel:
			with sequential:
				pulse("a", 100*MHz, 20*us)
				pulse("b", 100*MHz, 10*us)
			with sequential:
				pulse("A", 100*MHz, 10*us)
				pulse("B", 100*MHz, 10*us)
