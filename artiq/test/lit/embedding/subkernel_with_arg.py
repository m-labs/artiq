# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

@kernel
def entrypoint():
    # CHECK: call void @subkernel_load_run\(i32 1, i8 1, i1 true\), !dbg !.
    # CHECK: call void @subkernel_send_message\(i32 ., i1 false, i8 1, i8 1, .*\), !dbg !.
    accept_arg(1)


# CHECK-L: declare void @subkernel_load_run(i32, i8, i1) local_unnamed_addr
# CHECK-L: declare void @subkernel_send_message(i32, i1, i8, i8, { i8*, i32 }*, i8**) local_unnamed_addr
@subkernel(destination=1)
def accept_arg(arg: TInt32) -> TNone:
    pass
