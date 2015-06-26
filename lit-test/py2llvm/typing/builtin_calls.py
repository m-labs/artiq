# RUN: %python -m artiq.py2llvm.typing %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: bool:<built-in class bool>():bool
bool()

# CHECK-L: bool:<built-in class bool>([]:list(elt='a)):bool
bool([])

# CHECK-L: int:<built-in class int>():int(width='b)
int()

# CHECK-L: int:<built-in class int>(1.0:float):int(width='c)
int(1.0)

# CHECK-L: int:<built-in class int>(1.0:float, width=64:int(width='d)):int(width=64)
int(1.0, width=64)

# CHECK-L: float:<built-in class float>():float
float()

# CHECK-L: float:<built-in class float>(1:int(width='e)):float
float(1)

# CHECK-L: list:<built-in class list>():list(elt='f)
list()

# CHECK-L: len:<built-in function len>([]:list(elt='g)):int(width=32)
len([])

# CHECK-L: round:<built-in function round>(1.0:float):int(width='h)
round(1.0)
