# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

x = 1
# CHECK-L: x: numpy.int32

y = int(1)
# CHECK-L: y: numpy.int32

z = round(1.0)
# CHECK-L: z: numpy.int32
