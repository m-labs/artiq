# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    delay_mu(10)

# CHECK-L: ${LINE:+1}: fatal: delay delay(20 mu) was inferred for this function, but its delay is already constrained externally to delay(10 mu)
def g():
    delay_mu(20)

x = f if True else g
