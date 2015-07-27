# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: x:<function len>
x = len

def f():
    global len
    # CHECK-L: len:int(width='a) =
    len = 1
