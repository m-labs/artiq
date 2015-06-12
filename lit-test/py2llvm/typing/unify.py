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

i = []
i[0] = 1
# CHECK-L: i:list(elt=int(width='d))

j = []
j += [1.0]
# CHECK-L: j:list(elt=float)

1 if a else 2
# CHECK-L: 1:int(width='f) if a:int(width='a) else 2:int(width='f):int(width='f)

True and False
# CHECK-L: True:bool and False:bool:bool

1 and 0
# CHECK-L: 1:int(width='g) and 0:int(width='g):int(width='g)

~1
# CHECK-L: 1:int(width='h):int(width='h)

not 1
# CHECK-L: 1:int(width='i):bool
