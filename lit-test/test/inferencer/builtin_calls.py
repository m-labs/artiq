# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

# CHECK-L: bool:<constructor bool>():bool
bool()

# CHECK-L: bool:<constructor bool>([]:list(elt='a)):bool
bool([])

# CHECK-L: int:<constructor int>():int(width='b)
int()

# CHECK-L: int:<constructor int>(1.0:float):int(width='c)
int(1.0)

# CHECK-L: int:<constructor int>(1.0:float, width=64:int(width='d)):int(width=64)
int(1.0, width=64)

# CHECK-L: float:<constructor float>():float
float()

# CHECK-L: float:<constructor float>(1:int(width='e)):float
float(1)

# CHECK-L: list:<constructor list>():list(elt='f)
list()

# CHECK-L: len:<function len>([]:list(elt='g)):int(width=32)
len([])

# CHECK-L: round:<function round>(1.0:float):int(width='h)
round(1.0)
