# RUN: %python -m artiq.py2llvm.typing +diag %s >%t
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

# CHECK-L: ${LINE:+1}: error: py2llvm does not support passing tuples to '*'
(1,) * 2

# CHECK-L: ${LINE:+3}: error: expected '*' operands to be a list and an integer in this context
# CHECK-L: ${LINE:+2}: note: list operand of type list(elt=int(width='a))
# CHECK-L: ${LINE:+1}: note: operand of type list(elt='b), which is not a valid repetition amount
[1] * []

# CHECK-L: ${LINE:+3}: error: cannot coerce list(elt='a) and NoneType to a common numeric type
# CHECK-L: ${LINE:+2}: note: expression of type list(elt='a)
# CHECK-L: ${LINE:+1}: note: expression of type NoneType
[] - None

# CHECK-L: ${LINE:+2}: error: cannot coerce list(elt='a) to float
# CHECK-L: ${LINE:+1}: note: expression that required coercion to float
[] - 1.0
