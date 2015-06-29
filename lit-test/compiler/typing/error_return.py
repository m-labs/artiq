# RUN: %python -m artiq.compiler.typing +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+2}: error: cannot unify int(width='a) with NoneType
# CHECK-L: ${LINE:+1}: note: function with return type int(width='a)
def a():
    return 1
    # CHECK-L: ${LINE:+1}: note: a statement returning NoneType
    return

# CHECK-L: ${LINE:+2}: error: cannot unify int(width='a) with list(elt='b)
# CHECK-L: ${LINE:+1}: note: function with return type int(width='a)
def b():
    return 1
    # CHECK-L: ${LINE:+1}: note: a statement returning list(elt='b)
    return []
