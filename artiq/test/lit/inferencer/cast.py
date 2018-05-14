# RUN: %python -m artiq.compiler.testbench.inferencer +mono %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: 2:numpy.int64
int64(2)**32

# CHECK-L: round:<function round>(1.0:float):numpy.int64
int64(round(1.0))
