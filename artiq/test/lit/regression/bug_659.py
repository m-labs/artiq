# RUN: %python -m artiq.compiler.testbench.embedding %s

from artiq.language.core import *
from artiq.language.types import *
import numpy as np

@kernel
def rotate(array):
    '''Rotates an array, deleting the oldest value'''
    length = len(array)
    for i in range(np.int64(len(array)) - 1):
        array[length - i - 1] = array[length - i - 2]
    array[0] = 0

@kernel
def entrypoint():
    rotate([1,2,3,4])
