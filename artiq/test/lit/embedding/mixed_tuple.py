# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *

@kernel
def consume_tuple(x: TTuple([TInt32, TBool])):
    print(x)

@kernel
def return_tuple() -> TTuple([TInt32, TBool]):
    return (123, False)

@kernel
def entrypoint():
    consume_tuple(return_tuple())
