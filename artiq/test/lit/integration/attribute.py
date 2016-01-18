# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

r = range(10)
assert r.start == 0
assert r.stop == 10
assert r.step == 1
