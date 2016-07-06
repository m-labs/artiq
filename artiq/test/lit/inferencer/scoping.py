# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: []:list(elt=numpy.int?)
x = []

def f():
    global x
    x[0] = 1
