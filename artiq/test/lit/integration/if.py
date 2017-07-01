# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

if True:
    assert True

if False:
    assert False

if True:
    assert True
else:
    assert False

if False:
    assert False
else:
    assert True

assert (0 if True else 1) == 0
assert (0 if False else 1) == 1

if 0:
    assert True

if 1:
    assert True
