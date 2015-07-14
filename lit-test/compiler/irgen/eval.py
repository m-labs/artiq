# RUN: %python -m artiq.compiler.testbench.irgen %s >%t
# RUN: OutputCheck %s --file-to-check=%t

2 + 2
# CHECK-L: NoneType input.__modinit__() {
# CHECK-L: 1:
# CHECK-L:   %2 = int(width=32) eval `2 + 2`
# CHECK-L:   return NoneType None
# CHECK-L: }
