# RUN: %python -m artiq.compiler.testbench.inferencer %s >%t
# RUN: OutputCheck %s --file-to-check=%t

class c:
    a = 1
    def f():
        pass
    def m(self):
        pass

# CHECK-L: c:<constructor c {a: int(width='a), f: ()->NoneType delay('b), m: (self:<instance c>)->NoneType delay('c)}>
c
# CHECK-L: .a:int(width='a)
c.a
# CHECK-L: .f:()->NoneType delay('b)
c.f

# CHECK-L: .m:method(fn=(self:<instance c>)->NoneType delay('d), self=<instance c>)
c().m()
