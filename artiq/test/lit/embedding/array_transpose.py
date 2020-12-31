# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *
import numpy as np

@kernel
def entrypoint():
    # FIXME: This needs to be a runtime test (but numpy.* integration is
    # currently embedding-only).
    a = np.array([1, 2, 3])
    b = np.transpose(a)
    assert a.shape == b.shape
    for i in range(len(a)):
        assert a[i] == b[i]

    c = np.array([[1, 2, 3], [4, 5, 6]])
    d = np.transpose(c)
    assert c.shape == d.shape
    for i in range(2):
        for j in range(3):
            assert c[i][j] == d[j][i]
