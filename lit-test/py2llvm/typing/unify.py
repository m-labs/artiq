# RUN: %python -m artiq.py2llvm.typing %s >%t
# RUN: OutputCheck %s --file-to-check=%t

a = 1
# CHECK-L: a:int(width='a)

b = a
# CHECK-L: b:int(width='a)

c = True
# CHECK-L: c:bool

d = False
# CHECK-L: d:bool

e = None
# CHECK-L: e:NoneType

f = 1.0
# CHECK-L: f:float

g = []
# CHECK-L: g:list(elt='b)

h = [1]
# CHECK-L: h:list(elt=int(width='c))
