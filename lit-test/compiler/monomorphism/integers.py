# RUN: %python -m artiq.compiler.testbench.module %s >%t
# RUN: OutputCheck %s --file-to-check=%t

x = 1
# CHECK-L: x: int(width=32)
