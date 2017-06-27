# RUN: %python -m artiq.compiler.testbench.signature %s

def foo(x):
    if x:
        return 1
    else:
        return 2

foo(True)
