# RUN: %python -m artiq.compiler.testbench.inferencer +diag %s >%t
# RUN: OutputCheck %s --file-to-check=%t

class contextmgr:
    def __enter__(self, n1):
        pass

    def __exit__(self, n1, n2):
        pass

def foo():
    # CHECK-L: ${LINE:+2}: error: function '__enter__(self:<instance contextmgr>, n1:'a)->NoneType delay('b)' must accept 1 positional argument and no optional arguments
    # CHECK-L: ${LINE:+1}: error: function '__exit__(self:<instance contextmgr>, n1:'c, n2:'d)->NoneType delay('e)' must accept 4 positional arguments and no optional arguments
    with contextmgr():
        pass
