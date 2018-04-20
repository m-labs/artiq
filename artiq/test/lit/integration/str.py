# RUN: %python -m artiq.compiler.testbench.jit %s
# RUN: %python %s

assert "xy" == "xy"
assert not ("xy" == "xz")

assert "xy" != "xz"
assert not ("xy" != "xy")

assert ("x" + "y") == "xy"
