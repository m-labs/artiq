# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: def foo(val:bool)->numpy.int?:
def foo(val):
    return 1 if val else 0
