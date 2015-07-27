# RUN: %python -m artiq.compiler.testbench.module %s >%t

if False:
    x = 1
else:
    x = 2
-x
