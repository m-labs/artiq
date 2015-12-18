# RUN: %python -m artiq.compiler.testbench.signature +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    # CHECK-L: ${LINE:+1}: error: cannot interleave this 'with parallel:' statement
    with parallel:
        # CHECK-L: ${LINE:+1}: note: this 'return' statement transfers control out of the 'with parallel:' statement
        return
        delay(1.0)

def g():
    while True:
        # CHECK-L: ${LINE:+1}: error: cannot interleave this 'with parallel:' statement
        with parallel:
            # CHECK-L: ${LINE:+1}: note: this 'break' statement transfers control out of the 'with parallel:' statement
            break
            delay(1.0)
