# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *
from artiq.coredevice.exceptions import RTIOUnderflow

@kernel
def entrypoint():
    try:
        pass
    except RTIOUnderflow:
        pass
