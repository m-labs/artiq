# RUN: %python -m artiq.compiler.testbench.jit %s
# REQUIRES: exceptions

try:
    1/0
except ZeroDivisionError:
    # CHECK-L: OK
    print("OK")
