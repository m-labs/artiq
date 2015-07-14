# RUN: %python -m artiq.compiler.testbench.irgen %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: NoneType input.__modinit__() {
# CHECK-L: 1:
# CHECK-L:   return NoneType None
# CHECK-L: }
