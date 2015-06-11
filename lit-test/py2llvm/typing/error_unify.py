# RUN: %python -m artiq.py2llvm.typing +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

a = 1
b = []

# CHECK-L: ${LINE:+1}: error: cannot unify int(width='a) with list(elt='b)
a = b

# CHECK-L: ${LINE:+1}: error: cannot unify int(width='a) with list(elt='b)
[1, []]
# CHECK-L: note: a list of type list(elt=int(width='a))
# CHECK-L: note: a list element of type list(elt='b)

# CHECK-L: ${LINE:+1}: error: cannot unify int(width='a) with bool
1 and False
# CHECK-L: note: an operand of type int(width='a)
# CHECK-L: note: an operand of type bool
