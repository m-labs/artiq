# RUN: %python -m artiq.compiler.testbench.jit +load %personality %s
# REQUIRES: exceptions

1/0
