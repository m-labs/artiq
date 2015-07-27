# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: ${LINE:+1}: error: if clauses in comprehensions are not supported
[x for x in [] if x]

# CHECK-L: ${LINE:+1}: error: multiple for clauses in comprehensions are not supported
[(x, y) for x in [] for y in []]
