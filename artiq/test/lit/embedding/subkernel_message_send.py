# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

@kernel
def entrypoint():
    # CHECK: call void @subkernel_load_run\(i32 1, i8 1, i1 true\), !dbg !.
    message_pass()
    # CHECK: call void @subkernel_send_message\(i32 2, i1 false, i8 1, i8 1, .*\), !dbg !.
    # CHECK-NOT: call i8 @subkernel_await_message\(i32 1, i64 10000, { i8\*, i32 }\* nonnull .*, i8 1, i8 1\), !dbg !.
    subkernel_send(1, "message", 15)


# CHECK-L: declare void @subkernel_load_run(i32, i8, i1) local_unnamed_addr
# CHECK-L: declare void @subkernel_send_message(i32, i1, i8, i8, { i8*, i32 }*, i8**) local_unnamed_addr
@subkernel(destination=1)
def message_pass() -> TNone:
    subkernel_recv("message", TInt32)
