# RUN: %not %python -m artiq.compiler.testbench.jit %s
# REQUIRES: exceptions

# CHECK-L: Uncaught ZeroDivisionError: cannot divide by zero (0, 0, 0)
# CHECK-L: at input.py:${LINE:+1}:0
1/0
