# RUN: %python -m artiq.compiler.testbench.jit %s >%t
# RUN: OutputCheck %s --file-to-check=%t
# REQUIRES: time

def f():
    with watchdog(1.0):
        pass

def g():
    with watchdog(2.0):
        raise Exception()

def h():
    try:
        g()
    except:
        pass

def i():
    try:
        with watchdog(3.0):
            raise Exception()
    except:
        pass

# CHECK-L: watchdog_set 1000
# CHECK-L: watchdog_clear 1000
f()

# CHECK-L: watchdog_set 2000
# CHECK-L: watchdog_clear 2000
h()

# CHECK-L: watchdog_set 3000
# CHECK-L: watchdog_clear 3000
i()
