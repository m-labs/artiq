# RUN: %python -m artiq.compiler.testbench.signature +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

class Foo:
    def __init__(self):
        pass

a = Foo()
b = Foo()

# CHECK-L: ${LINE:+1}: error: Custom object comparison is not supported
a > b

