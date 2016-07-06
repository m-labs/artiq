# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t

def _gcd(a, b):
    if a < 0:
        a = -a
    while a:
        c = a
        a = b % a
        b = c
    return b

# CHECK-L: _gcd:(a:numpy.int?, b:numpy.int?)->numpy.int?(10:numpy.int?, 25:numpy.int?):numpy.int?
_gcd(10, 25)
