# RUN: %python -m artiq.compiler.testbench.jit %s
# REQUIRES: time

with parallel:
    with sequential:
        assert now_mu() == 0
        delay_mu(10)
        assert now_mu() == 10
    with sequential:
        assert now_mu() == 0
        delay_mu(20)
        assert now_mu() == 20
    with sequential:
        assert now_mu() == 0
        delay_mu(15)
        assert now_mu() == 15
    assert now_mu() == 0
assert now_mu() == 20
