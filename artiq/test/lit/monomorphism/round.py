# RUN: %python -m artiq.compiler.testbench.inferencer +mono %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: round:<function round>(1.0:float):numpy.int32
round(1.0)

# CHECK-L: round:<function round>(2.0:float):numpy.int32
int32(round(2.0))

# CHECK-L: round:<function round>(3.0:float):numpy.int64
int64(round(3.0))
