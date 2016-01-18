# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

class contextmgr:
    def __enter__(self):
        return 1

    def __exit__(self, n1, n2, n3):
        pass

def foo():
    x = "x"
    # CHECK-L: ${LINE:+3}: error: cannot unify str with NoneType
    # CHECK-L: ${LINE:+2}: note: expression of type str
    # CHECK-L: ${LINE:+1}: note: context manager with an '__enter__' method returning NoneType
    with contextmgr() as x:
        pass
