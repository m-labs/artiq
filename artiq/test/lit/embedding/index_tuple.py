# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: void @_Z16testbench.unpackzz({ i32, { i8*, i32 }, i1 } %ARG.x)

@kernel
def unpack(x):
    print(x[0])

@kernel
def entrypoint():
    unpack((1, "foo", True))
    unpack((2, "bar", False))
