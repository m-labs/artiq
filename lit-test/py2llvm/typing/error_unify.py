# RUN: %python -m artiq.py2llvm.typing +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

a = 1
b = []

# CHECK-L: ${LINE:+1}: fatal: cannot unify int(width='a) with list(elt='b)
a = b
