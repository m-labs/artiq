# RUN: %not %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def f():
    1/0

def g():
    try:
        f()
    except Exception as e:
        # CHECK-L: Uncaught 0:ZeroDivisionError
        # CHECK-L: at input.py:${LINE:+1}:
        raise e

g()
