# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

class c:
    a = 1
    def f():
        pass
    def m(self):
        pass

# CHECK-L: c:<constructor c {a: numpy.int?, f: ()->NoneType delay('a), m: (self:<instance c>)->NoneType delay('b)}>
c
# CHECK-L: .a:numpy.int?
c.a
# CHECK-L: .f:()->NoneType delay('a)
c.f

# CHECK-L: .m:method(fn=(self:<instance c>)->NoneType delay('b), self=<instance c>)
c().m()
