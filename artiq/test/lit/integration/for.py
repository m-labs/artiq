# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

count = 0
for x in range(10):
    count += 1
assert count == 10

for x in range(10):
    assert True
else:
    assert True

for x in range(0):
    assert False
else:
    assert True

for x in range(10):
    continue
    assert False
else:
    assert True

for x in range(10):
    break
    assert False
else:
    assert False

# Verify continue target is reset in else block.
cond = False
while True:
    if cond:
        break
    cond = True
    for _ in range(1):
        pass
    else:
        continue
    assert False
else:
    assert False

# Verify for target is reset in else block.
while True:
    for _ in range(1):
        pass
    else:
        break
    assert False
else:
    assert False
