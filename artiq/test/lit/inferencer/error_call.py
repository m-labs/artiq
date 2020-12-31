# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: cannot call this expression of type numpy.int?
(1)()

def f(x, y, z=1):
    pass

# CHECK-L: ${LINE:+1}: error: variadic arguments are not supported
f(*[])

# CHECK-L: ${LINE:+1}: error: variadic arguments are not supported
f(**[])

# CHECK-L: ${LINE:+1}: error: the argument 'x' has been passed earlier as positional
f(1, x=1)

# CHECK-L: ${LINE:+1}: error: mandatory argument 'x' is not passed
f()

# CHECK: ${LINE:+1}: error: this function of type .* does not accept argument 'q'
f(1, q=1)
