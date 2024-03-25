import numpy as np


def is_valid_int(i, type):
    info = np.iinfo(type)
    return info.min <= i <= info.max
