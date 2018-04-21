# RUN: %python -m artiq.compiler.testbench.inferencer +mono %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: n:numpy.int32 =
n = 0
# CHECK-L: a:numpy.int32 =
a = n // 1
# CHECK-L: b:numpy.int32 =
b = n // 10
# CHECK-L: q:numpy.int64 =
q = (a << 0) + (b << 8)
core_log(int64(q))
