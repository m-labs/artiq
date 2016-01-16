# RUN: %python -m artiq.compiler.testbench.signature %s

def f():
    x, y = [0], [0]
    x[0], y[0]
