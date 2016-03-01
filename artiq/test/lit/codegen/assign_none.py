# RUN: %python -m artiq.compiler.testbench.llvmgen %s

def f():
    pass
def g():
    a = f()
