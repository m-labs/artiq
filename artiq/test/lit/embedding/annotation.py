# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

# CHECK: i64 @_Z13testbench.foozz\(i64 %ARG.x, \{ i1, i64 \} %ARG.y\)

@kernel
def foo(x: TInt64, y: TInt64 = 1) -> TInt64:
    print(x+y)
    return x+y

@kernel
def bar(x: TInt64) -> None:
    print(x)

@kernel
def entrypoint():
    print(foo(0, 2))
    print(foo(1, 3))
    bar(3)
