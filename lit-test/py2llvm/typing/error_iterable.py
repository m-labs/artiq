# RUN: %python -m artiq.py2llvm.typing +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: type int(width='a) is not iterable
for x in 1: pass
