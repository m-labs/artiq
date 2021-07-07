# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *
import numpy as np

n = 2
data = np.zeros((n, n))


@kernel
def entrypoint():
    print(data[:n])
