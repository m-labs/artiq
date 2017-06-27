# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

a = 1
# CHECK-L: a:numpy.int?

b = a
# CHECK-L: b:numpy.int?

c = True
# CHECK-L: c:bool

d = False
# CHECK-L: d:bool

e = None
# CHECK-L: e:NoneType

f = 1.0
# CHECK-L: f:float

g = []
# CHECK-L: g:list(elt='a)

h = [1]
# CHECK-L: h:list(elt=numpy.int?)

i = []
i[0] = 1
# CHECK-L: i:list(elt=numpy.int?)

j = []
j += [1.0]
# CHECK-L: j:list(elt=float)

1 if a else 2
# CHECK-L: 1:numpy.int? if a:numpy.int? else 2:numpy.int?:numpy.int?

True and False
# CHECK-L: True:bool and False:bool:bool

1 and 0
# CHECK-L: 1:numpy.int? and 0:numpy.int?:numpy.int?

~1
# CHECK-L: 1:numpy.int?:numpy.int?

not 1
# CHECK-L: 1:numpy.int?:bool

[x for x in [1]]
# CHECK-L: [x:numpy.int? for x:numpy.int? in [1:numpy.int?]:list(elt=numpy.int?)]:list(elt=numpy.int?)

lambda x, y=1: x
# CHECK-L: lambda x:'b, y:numpy.int?=1:numpy.int?: x:'b:(x:'b, ?y:numpy.int?)->'b

k = "x"
# CHECK-L: k:str

ka = b"x"
# CHECK-L: ka:bytes

kb = bytearray(b"x")
# CHECK-L: kb:bytearray

l = array([1])
# CHECK-L: l:numpy.array(elt=numpy.int?)

IndexError()
# CHECK-L: IndexError:<constructor IndexError {}>():IndexError

IndexError("x")
# CHECK-L: IndexError:<constructor IndexError>("x":str):IndexError

IndexError("x", 1)
# CHECK-L: IndexError:<constructor IndexError>("x":str, 1:numpy.int64):IndexError

IndexError("x", 1, 1)
# CHECK-L: IndexError:<constructor IndexError>("x":str, 1:numpy.int64, 1:numpy.int64):IndexError

IndexError("x", 1, 1, 1)
# CHECK-L: IndexError:<constructor IndexError>("x":str, 1:numpy.int64, 1:numpy.int64, 1:numpy.int64):IndexError
