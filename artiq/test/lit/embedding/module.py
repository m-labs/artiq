# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *

import time, os

@kernel
def entrypoint():
    time.sleep(10)
    os.mkdir("foo")
