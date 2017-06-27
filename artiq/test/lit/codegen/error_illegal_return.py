# RUN: %python -m artiq.compiler.testbench.signature +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: this function must return a value of type numpy.int32 explicitly
def foo(x):
    if x:
        return 1

foo(True)
