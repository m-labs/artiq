# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

x = [0]
# CHECK-L: [::numpy.int32]
x[:] = [1]
