# RUN: %python -m artiq.py2llvm.typing %s >%t

def _gcd(a, b):
    if a < 0:
        a = -a
    while a:
        c = a
        a = b % a
        b = c
    return b

_gcd(10, 25)
