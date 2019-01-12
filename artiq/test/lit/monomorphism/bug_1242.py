# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

x = 0x100000000
# CHECK-L: x: numpy.int64

y = int32(x)
# CHECK-L: y: numpy.int32
