# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

class contextmgr:
    def __enter__(self):
        pass

    def __exit__(self, n1, n2, n3):
        pass

def foo():
    contextmgr.__enter__(1)
    # CHECK-L: ${LINE:+3}: error: cannot unify <instance contextmgr> with numpy.int? while inferring the type for self argument
    # CHECK-L: ${LINE:+2}: note: expression of type <instance contextmgr {}>
    # CHECK-L: ${LINE:+1}: note: reference to an instance with a method '__enter__(self:numpy.int?)->NoneType delay('a)'
    with contextmgr():
        pass
