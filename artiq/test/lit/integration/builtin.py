# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s
# REQUIRES: exceptions

assert bool() is False
# bool(x) is tested in bool.py

assert int() is 0
assert int(1.0) is 1
#ARTIQ#assert int64(1) << 40 is 1099511627776

#ARTIQ#assert float() is 0.0
#ARTIQ#assert float(1) is 1.0

x = list()
if False: x = [1]
assert x == []

#ARTIQ#assert range(10) is range(0, 10, 1)
#ARTIQ#assert range(1, 10) is range(1, 10, 1)

assert len([1, 2, 3]) is 3
assert len(range(10)) is 10
assert len(range(0, 10, 2)) is 5

#ARTIQ#assert round(1.4) is 1 and round(1.6) is 2
