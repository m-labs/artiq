# RUN: %python -m artiq.py2llvm.typing %s >%t
# RUN: OutputCheck %s --file-to-check=%t

1 | 2
# CHECK-L: 1:int(width='a):int(width='b) | 2:int(width='c):int(width='b):int(width='b)

1 + 2
# CHECK-L: 1:int(width='d):int(width='e) + 2:int(width='f):int(width='e):int(width='e)

(1,) + (2.0,)
# CHECK-L: (1:int(width='g),):(int(width='g),) + (2.0:float,):(float,):(int(width='g), float)

[1] + [2]
# CHECK-L: [1:int(width='h)]:list(elt=int(width='h)) + [2:int(width='h)]:list(elt=int(width='h)):list(elt=int(width='h))

1 * 2
# CHECK-L: 1:int(width='i):int(width='j) * 2:int(width='k):int(width='j):int(width='j)

[1] * 2
# CHECK-L: [1:int(width='l)]:list(elt=int(width='l)) * 2:int(width='m):list(elt=int(width='l))

1 / 2
# CHECK-L: 1:int(width='n):int(width='o) / 2:int(width='p):int(width='o):int(width='o)

1 + 1.0
# CHECK-L: 1:int(width='q):float + 1.0:float:float

a = []; a += [1]
# CHECK-L: a:list(elt=int(width='r)) = []:list(elt=int(width='r)); a:list(elt=int(width='r)) += [1:int(width='r)]:list(elt=int(width='r))
