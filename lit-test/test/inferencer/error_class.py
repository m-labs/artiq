# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: inheritance is not supported
class a(1):
    pass

class b:
    # CHECK-L: ${LINE:+1}: fatal: class body must contain only assignments and function definitions
    x += 1
