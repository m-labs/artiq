# RUN: %python -m artiq.compiler.testbench.irgen %s >%t
# RUN: OutputCheck %s --file-to-check=%t

def x(y): pass

# CHECK-L: NoneType input.a(environment(...) %ARG.ENV, NoneType %ARG.self) {
# CHECK-L: setlocal('self') %ENV, NoneType %ARG.self
# CHECK-NOT-L: call (y:NoneType)->NoneType %LOC.x, NoneType %ARG.self

def a(self):
    def b():
        pass
    x(self)

a(None)
