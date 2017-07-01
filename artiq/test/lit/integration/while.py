# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

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

# Verify continue target is reset in else block.
cond = False
while True:
    if cond:
        break
    cond = True
    while False:
        assert False
    else:
        continue
    assert False
else:
    assert False

# Verify break target is reset in else block.
while True:
    while False:
        assert False
    else:
        break
    assert False
else:
    assert False

while 0:
    assert False

while 1:
    assert True
    break
