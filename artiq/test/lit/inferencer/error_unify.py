# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

a = 1
b = []

# CHECK-L: ${LINE:+1}: error: cannot unify numpy.int? with list(elt='a)
a = b

# CHECK-L: ${LINE:+1}: error: cannot unify numpy.int? with list(elt='a)
[1, []]
# CHECK-L: note: a list element of type numpy.int?
# CHECK-L: note: a list element of type list(elt='a)

# CHECK-L: ${LINE:+1}: error: cannot unify numpy.int? with bool
1 and False
# CHECK-L: note: an operand of type numpy.int?
# CHECK-L: note: an operand of type bool

# CHECK-L: ${LINE:+1}: error: expected unary '+' operand to be of numeric type, not list(elt='a)
+[]

# CHECK-L: ${LINE:+1}: error: expected '~' operand to be of integer type, not float
~1.0

# CHECK-L: ${LINE:+1}: error: type numpy.int? does not have an attribute 'x'
(1).x
