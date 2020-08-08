# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
import numpy as np

@kernel
def entrypoint():
    # Just make sure everything compiles.
    a = np.array([1.0, 2.0, 3.0])
    b = np.sin(a)
    assert b.shape == a.shape

    c = np.array([1.0, 2.0, 3.0])
    d = np.arctan(c)
    assert d.shape == c.shape
