# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

a = 1
b = []

# CHECK-L: ${LINE:+1}: error: cannot unify int(width='a) with list(elt='b)
a = b

# CHECK-L: ${LINE:+1}: error: cannot unify int(width='a) with list(elt='b)
[1, []]
# CHECK-L: note: a list element of type int(width='a)
# CHECK-L: note: a list element of type list(elt='b)

# CHECK-L: ${LINE:+1}: error: cannot unify int(width='a) with bool
1 and False
# CHECK-L: note: an operand of type int(width='a)
# CHECK-L: note: an operand of type bool

# CHECK-L: ${LINE:+1}: error: expected unary '+' operand to be of numeric type, not list(elt='a)
+[]

# CHECK-L: ${LINE:+1}: error: expected '~' operand to be of integer type, not float
~1.0

# CHECK-L: ${LINE:+1}: error: type int(width='a) does not have an attribute 'x'
(1).x
