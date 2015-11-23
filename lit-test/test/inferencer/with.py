# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: as x:<function parallel>
with parallel as x: pass
