# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *
from numpy import array

int_vec = array([1, 2, 3])
float_vec = array([1.0, 2.0, 3.0])
int_mat = array([[1, 2], [3, 4]])
float_mat = array([[1.0, 2.0], [3.0, 4.0]])


@kernel
def entrypoint():
    # TODO: These need to be runtime tests!
    assert int_vec.shape == (3, )
    assert int_vec[0] == 1
    assert int_vec[1] == 2
    assert int_vec[2] == 3

    assert float_vec.shape == (3, )
    assert float_vec[0] == 1.0
    assert float_vec[1] == 2.0
    assert float_vec[2] == 3.0

    assert int_mat.shape == (2, 2)
    assert int_mat[0][0] == 1
    assert int_mat[0][1] == 2
    assert int_mat[1][0] == 3
    assert int_mat[1][1] == 4

    assert float_mat.shape == (2, 2)
    assert float_mat[0][0] == 1.0
    assert float_mat[0][1] == 2.0
    assert float_mat[1][0] == 3.0
    assert float_mat[1][1] == 4.0
