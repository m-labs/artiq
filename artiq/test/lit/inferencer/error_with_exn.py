# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

class contextmgr:
    def __enter__(self):
        pass

    def __exit__(self, n1, n2, n3):
        n3 = 1
        pass

def foo():
    # CHECK-L: ${LINE:+2}: error: cannot unify numpy.int? with NoneType
    # CHECK-L: ${LINE:+1}: note: exception handling via context managers is not supported; the argument 'n3' of function '__exit__(self:<instance contextmgr>, n1:NoneType, n2:NoneType, n3:numpy.int?)->NoneType delay('a)' will always be None
    with contextmgr():
        pass
