# RUN: %python -m artiq.compiler.testbench.embedding +diag %s 2>%t
# RUN: OutputCheck %s --file-to-check=%t

from artiq.language.core import *
from artiq.language.types import *

@kernel
def f(self):
    core_log(self.x)
class c:
    a = f
    x = 1
class d:
    b = f
    x = 2
xa = c().a
xb = d().b

@kernel
def entrypoint():
    xa()
    # CHECK-L: <synthesized>:1: error: cannot unify <instance testbench.d> with <instance testbench.c
    # CHECK-L: ${LINE:+1}: note: expanded from here
    xb()
