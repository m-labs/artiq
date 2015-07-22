# RUN: %python -m artiq.compiler.testbench.jit %s

cond, count = True, 0
while cond:
    count += 1
    cond = False
assert count == 1

while False:
    pass
else:
    assert True

cond = True
while cond:
    cond = False
else:
    assert True

while True:
    break
    assert False
else:
    assert False

cond = True
while cond:
    cond = False
    continue
    assert False
