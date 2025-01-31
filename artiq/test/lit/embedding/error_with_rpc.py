# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.experiment import kernel

class contextmgr:
    def __enter__(self):
        pass

    @kernel
    def __exit__(self, n1, n2, n3):
        pass

c = contextmgr()

@kernel
def entrypoint():
    # CHECK-L: ${LINE:+1}: error: function '__enter__[rpc2 #](...)->NoneType' must be a @kernel
    with c:
        pass
