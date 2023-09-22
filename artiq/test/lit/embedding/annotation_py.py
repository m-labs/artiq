# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from typing import List, Tuple

import numpy as np

from artiq.language.core import *
from artiq.language.types import *

# CHECK-L: i64 @_Z13testbench.foozz(i64 %ARG.x, { i1, i32 } %ARG.y)

@kernel
def foo(x: np.int64, y: np.int32 = 1) -> np.int64:
    print(x + y)
    return x + y

# CHECK-L: void @_Z13testbench.barzz()
@kernel
def bar(x: np.int32) -> None:
    print(x)

# CHECK-L: @_Z21testbench.unpack_listzz({ i1, i64 }* nocapture writeonly sret({ i1, i64 }) %.1, { i64*, i32 }* %ARG.xs)
@kernel
def unpack_list(xs: List[np.int64]) -> Tuple[bool, np.int64]:
    print(xs)
    return (len(xs) == 1, xs[0])

@kernel
def entrypoint():
    print(foo(0, 2))
    print(foo(1, 3))
    bar(3)
    print(unpack_list([1, 2, 3]))
