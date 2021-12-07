# RUN: env ARTIQ_DUMP_LLVM=%t %python -m artiq.compiler.testbench.embedding +compile %s
# RUN: OutputCheck %s --file-to-check=%t.ll

from artiq.language.core import *
from artiq.language.types import *

# Make sure `byval` and `sret` are specified both at the call site and the
# declaration. This isn't caught by the LLVM IR validator, but mismatches
# lead to miscompilations (at least in LLVM 11).


@kernel
def entrypoint():
    # CHECK: call void @accept_str\({ i8\*, i32 }\* nonnull byval
    accept_str("foo")

    # CHECK: call void @return_str\({ i8\*, i32 }\* nonnull sret
    return_str()


# CHECK: declare void @accept_str\({ i8\*, i32 }\* byval\)
@syscall
def accept_str(name: TStr) -> TNone:
    pass


# CHECK: declare void @return_str\({ i8\*, i32 }\* sret\)
@syscall
def return_str() -> TStr:
    pass
