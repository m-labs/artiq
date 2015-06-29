# RUN: %python -m artiq.compiler.typing +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: fatal: name 'x' is not bound to anything
x
