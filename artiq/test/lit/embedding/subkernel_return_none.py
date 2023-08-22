# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

@kernel
def entrypoint():
    # CHECK: call void @subkernel_load_run\(i32 1, i1 true\), !dbg !.
    # CHECK-NOT: call void @subkernel_send_message\(.*\), !dbg !.
    returning_none()
    # CHECK: call void @subkernel_await_finish\(i1 false, i32 1, i64 10000\), !dbg !.
    # CHECK-NOT: call void @subkernel_await_message\(i32 1, i64 10000\), !dbg !.
    subkernel_await(returning_none)

# CHECK-L: declare void @subkernel_load_run(i32, i1) local_unnamed_addr
# CHECK-NOT-L: declare void @subkernel_send_message(i32, { i8*, i32 }*, i8**) local_unnamed_addr
# CHECK-L: declare void @subkernel_await_finish(i1, i32, i64) local_unnamed_addr
# CHECK-NOT-L: declare void @subkernel_await_message(i32, i64) local_unnamed_addr
@subkernel(destination=1)
def returning_none() -> TNone:
    pass
