# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

class c:
    def f():
        pass

    def g(self):
        pass

# CHECK-L: ${LINE:+1}: error: function 'f()->NoneType delay('a)' of class 'c' cannot accept a self argument
c().f()

c.g(1)
# CHECK-L: ${LINE:+1}: error: cannot unify <instance c> with numpy.int? while inferring the type for self argument
c().g()
