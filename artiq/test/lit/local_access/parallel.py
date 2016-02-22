# RUN: %python -m artiq.compiler.testbench.signature %s >%t

with interleave:
    delay(1.0)
    t0 = now_mu()
print(t0)
