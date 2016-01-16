# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

class c:
    pass
# CHECK-L: ${LINE:+1}: fatal: variable 'c' is already defined
class c:
    pass
