# RUN: %python -m artiq.compiler.testbench.irgen %s >%t
# RUN: OutputCheck %s --file-to-check=%t

while 1:
    2
else:
    3
4

# CHECK-L: NoneType input.__modinit__() {
# CHECK-L: 1:
# CHECK-L:   branch ssa.basic_block %2
# CHECK-L: 2:
# CHECK-L:   %9 = int(width=32) eval `1`
# CHECK-L:   branch_if int(width=32) %9, ssa.basic_block %5, ssa.basic_block %7
# CHECK-L: 4:
# CHECK-L:   branch ssa.basic_block %7
# CHECK-L: 5:
# CHECK-L:   %6 = int(width=32) eval `2`
# CHECK-L:   branch ssa.basic_block %7
# CHECK-L: 7:
# CHECK-L:   %8 = int(width=32) eval `3`
# CHECK-L:   %13 = int(width=32) eval `4`
# CHECK-L:   return NoneType None
# CHECK-L: }
