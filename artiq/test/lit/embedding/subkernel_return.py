# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

@kernel
def entrypoint():
    # CHECK: call void @subkernel_load_run\(i32 1, i8 1, i1 true\), !dbg !.
    # CHECK-NOT: call void @subkernel_send_message\(.*\), !dbg !.
    returning()
    # CHECK: call i8 @subkernel_await_message\(i32 1, i64 -1, { i8\*, i32 }\* nonnull .*, i8 1, i8 1\), !dbg !.
    # CHECK: call void @subkernel_await_finish\(i32 1, i64 -1\), !dbg !.
    subkernel_await(returning)

# CHECK-L: declare void @subkernel_load_run(i32, i8, i1) local_unnamed_addr
# CHECK-NOT-L: declare void @subkernel_send_message(i32, i1, i8, i8, { i8*, i32 }*, i8**) local_unnamed_addr
# CHECK-L: declare i8 @subkernel_await_message(i32, i64, { i8*, i32 }*, i8, i8) local_unnamed_addr
# CHECK-L: declare void @subkernel_await_finish(i32, i64) local_unnamed_addr
@subkernel(destination=1)
def returning() -> TInt32:
    return 1
