# RUN: %not %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: exceptions

def f():
    # CHECK-L: Uncaught 8
    # CHECK-L: at input.py:${LINE:+1}:
    1/0

def g():
    try:
        f()
    except:
        raise

g()
