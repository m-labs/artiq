# RUN: %python -m artiq.compiler.typing %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    global x
    x = 1
# CHECK-L: [x:int(width='a)]
[x]
