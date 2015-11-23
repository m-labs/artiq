# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

try:
    1/0
except ZeroDivisionError:
    # CHECK-L: OK
    print("OK")
