# RUN: %python -m artiq.py2llvm.typing %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: x:<built-in function len>
x = len

def f():
    global len
    # CHECK-L: len:int(width='a) =
    len = 1
