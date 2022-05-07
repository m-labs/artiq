# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

# CHECK: call void @foo\(\)(, !dbg !\d+)?

# CHECK-L: ; Function Attrs: inaccessiblememonly nounwind
# CHECK-NEXT-L: declare void @foo()

@syscall(flags={"nounwind", "nowrite"})
def foo() -> TNone:
    pass

# sret nowrite functions shouldn't be marked inaccessiblememonly.
# CHECK-L: ; Function Attrs: nounwind
# CHECK-NEXT-L: declare void @bar({ i32, i64 }* sret)
@syscall(flags={"nounwind", "nowrite"})
def bar() -> TTuple([TInt32, TInt64]):
    pass

@kernel
def entrypoint():
    foo()
    bar()
