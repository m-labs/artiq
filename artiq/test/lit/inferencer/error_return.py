# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+2}: error: cannot unify numpy.int? with NoneType
# CHECK-L: ${LINE:+1}: note: function with return type numpy.int?
def a():
    return 1
    # CHECK-L: ${LINE:+1}: note: a statement returning NoneType
    return

# CHECK-L: ${LINE:+2}: error: cannot unify numpy.int? with list(elt='a)
# CHECK-L: ${LINE:+1}: note: function with return type numpy.int?
def b():
    return 1
    # CHECK-L: ${LINE:+1}: note: a statement returning list(elt='a)
    return []
