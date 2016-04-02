import numpy as np
from numba import jit
from scipy.optimize import least_squares


@jit(nopython=True)
def compute_gaussian(r, img_w, img_h,
                     gaussian_w, gaussian_h,
                     gaussian_cx, gaussian_cy):
    for y in range(img_h):
        for x in range(img_w):
            ds = ((gaussian_cx-x)/gaussian_w)**2 
            ds += ((gaussian_cy-y)/gaussian_h)**2
            r[x, y] = np.exp(-ds/2)


def fit(data):
    img_w, img_h = data.shape
    def err(parameters):
        r = np.empty((img_w, img_h))
        compute_gaussian(r, img_w, img_h, *parameters)
        r -= data
        return r.ravel()
    guess = [12, 15, img_w/2, img_h/2]
    res = least_squares(err, guess)
    return res.x


def get_and_fit():
    return fit(controller_driver.get_picture())
