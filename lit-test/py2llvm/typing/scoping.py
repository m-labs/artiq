# RUN: %python -m artiq.py2llvm.typing %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def f():
    global x
    x = 1
# CHECK-L: [x:int(width='a)]
[x]
