# RUN: %python -m artiq.compiler.testbench.signature +diag +delay %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    for _ in range(10):
        delay_mu(10)
        # CHECK-L: ${LINE:+1}: error: loop iteration count is indeterminate because of control flow
        break

def g():
    for _ in range(10):
        delay_mu(10)
        # CHECK-L: ${LINE:+1}: error: loop iteration count is indeterminate because of control flow
        continue
