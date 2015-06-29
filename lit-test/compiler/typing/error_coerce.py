# RUN: %python -m artiq.compiler.typing +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: expected '<<' operand to be of integer type, not float
1 << 2.0

# CHECK-L: ${LINE:+3}: error: expected every '+' operand to be a list in this context
# CHECK-L: ${LINE:+2}: note: list of type list(elt=int(width='a))
# CHECK-L: ${LINE:+1}: note: int(width='b), which cannot be added to a list
[1] + 2

# CHECK-L: ${LINE:+1}: error: cannot unify list(elt=int(width='a)) with list(elt=float): int(width='a) is incompatible with float
[1] + [2.0]

# CHECK-L: ${LINE:+3}: error: expected every '+' operand to be a tuple in this context
# CHECK-L: ${LINE:+2}: note: tuple of type (int(width='a),)
# CHECK-L: ${LINE:+1}: note: int(width='b), which cannot be added to a tuple
(1,) + 2

# CHECK-L: ${LINE:+1}: error: passing tuples to '*' is not supported
(1,) * 2

# CHECK-L: ${LINE:+3}: error: expected '*' operands to be a list and an integer in this context
# CHECK-L: ${LINE:+2}: note: list operand of type list(elt=int(width='a))
# CHECK-L: ${LINE:+1}: note: operand of type list(elt='b), which is not a valid repetition amount
[1] * []

# CHECK-L: ${LINE:+1}: error: cannot coerce list(elt='a) to a numeric type
[] - 1.0

# CHECK-L: ${LINE:+2}: error: expression of type int(width='a) has to be coerced to float, which makes assignment invalid
# CHECK-L: ${LINE:+1}: note: expression of type float
a = 1; a += 1.0

# CHECK-L: ${LINE:+2}: error: the result of this operation has type (int(width='a), float), which makes assignment to a slot of type (int(width='a),) invalid
# CHECK-L: ${LINE:+1}: note: expression of type (float,)
b = (1,); b += (1.0,)
