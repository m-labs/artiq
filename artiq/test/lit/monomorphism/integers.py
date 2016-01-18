# RUN: %python -m artiq.compiler.testbench.signature %s >%t
# RUN: OutputCheck %s --file-to-check=%t

x = 1
# CHECK-L: x: int(width=32)

y = int(1)
# CHECK-L: y: int(width=32)

z = round(1.0)
# CHECK-L: z: int(width=32)
