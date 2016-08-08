# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert ("x" + "y") == "xy"
