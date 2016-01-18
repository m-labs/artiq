# RUN: %python -m artiq.compiler.testbench.jit %s

assert seconds_to_mu(2.0) == 2000000
assert mu_to_seconds(1500000) == 1.5
