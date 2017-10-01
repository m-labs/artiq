# RUN: %python %s
# RUN: %python -m artiq.compiler.testbench.jit %s
# REQUIRES: exceptions

assert -(-1) == 1
assert -(-1.0) == 1.0
assert +1 == 1
assert +1.0 == 1.0
assert 1 + 1 == 2
assert 1.0 + 1.0 == 2.0
assert 1 - 1 == 0
assert 1.0 - 1.0 == 0.0
assert 2 * 2 == 4
assert 2.0 * 2.0 == 4.0
assert 3 / 2 == 1.5
assert 3.0 / 2.0 == 1.5
assert 3 // 2 == 1
assert 3.0 // 2.0 == 1.0
assert 3 % 2 == 1
assert -3 % 2 == 1
assert 3 % -2 == -1
assert -3 % -2 == -1
assert -1 % 8 == 7
#ARTIQ#assert int64(3) % 2 == 1
#ARTIQ#assert int64(-3) % 2 == 1
#ARTIQ#assert int64(3) % -2 == -1
#ARTIQ#assert int64(-3) % -2 == -1
assert -1 % 8 == 7
assert 3.0 % 2.0 == 1.0
assert -3.0 % 2.0 == 1.0
assert 3.0 % -2.0 == -1.0
assert -3.0 % -2.0 == -1.0
assert 3 ** 2 == 9
assert 3.0 ** 2.0 == 9.0
assert 9.0 ** 0.5 == 3.0
assert 1 << 1 == 2
assert 2 >> 1 == 1
assert -2 >> 1 == -1
#ARTIQ#assert 1 << 32 == 0
assert -1 >> 32 == -1
assert 0x18 & 0x0f == 0x08
assert 0x18 | 0x0f == 0x1f
assert 0x18 ^ 0x0f == 0x17
#ARTIQ#assert ~0x18 == -25
#ARTIQ#assert ~int64(0x18) == -25

try:
    1 / 0
except ZeroDivisionError:
    pass
else:
    assert False
try:
    1 // 0
except ZeroDivisionError:
    pass
else:
    assert False
try:
    1 % 0
except ZeroDivisionError:
    pass
else:
    assert False
