# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.experiment import *

class c():
# CHECK-L: ${LINE:+2}: error: type annotation for argument 'x', '<class 'list'>', is not an ARTIQ type
    @kernel
    def hello(self, x: list):
        pass

    @kernel
    def run(self):
        self.hello([])

i = c()
@kernel
def entrypoint():
    i.run()
