# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert "xy" == "xy"
assert ("x" + "y") == "xy"
