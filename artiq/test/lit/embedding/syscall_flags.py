# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

# CHECK: call void @foo\(\)(, !dbg !\d+)?, !tbaa !\d+

# CHECK-L: ; Function Attrs: nounwind
# CHECK-NEXT-L: declare void @foo()

@syscall(flags={"nounwind", "nowrite"})
def foo() -> TNone:
    pass

@kernel
def entrypoint():
    foo()
