# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t

def _gcd(a, b):
    if a < 0:
        a = -a
    while a:
        c = a
        a = b % a
        b = c
    return b

# CHECK-L: _gcd:(a:int(width='a), b:int(width='a))->int(width='a)(10:int(width='a), 25:int(width='a)):int(width='a)
_gcd(10, 25)
