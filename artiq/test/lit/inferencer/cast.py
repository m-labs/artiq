# RUN: %python -m artiq.compiler.testbench.inferencer +mono %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: numpy.int64
int64(2)**32
