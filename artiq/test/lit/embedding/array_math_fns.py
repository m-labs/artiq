# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
import numpy as np

@kernel
def entrypoint():
    # Just make sure everything compiles.

    # LLVM intrinsic:
    a = np.array([1.0, 2.0, 3.0])
    b = np.sin(a)
    assert b.shape == a.shape

    # libm:
    c = np.array([1.0, 2.0, 3.0])
    d = np.arctan(c)
    assert d.shape == c.shape

    # libm, binary:
    e = np.array([1.0, 2.0, 3.0])
    f = np.array([4.0, 5.0, 6.0])
    g = np.arctan2(e, f)
    # g = np.arctan2(e, 0.0)
    # g = np.arctan2(0.0, f)
    assert g.shape == e.shape
