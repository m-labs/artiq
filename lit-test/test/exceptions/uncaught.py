# RUN: %not %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

# CHECK-L: Uncaught 0:ZeroDivisionError: cannot divide by zero (0, 0, 0)
# CHECK-L: at input.py:${LINE:+1}:
1/0
