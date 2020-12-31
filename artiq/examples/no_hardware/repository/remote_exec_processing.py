import numpy as np
from numba import jit
from scipy.optimize import least_squares
import logging


logger = logging.getLogger(__name__)


@jit(nopython=True)
def compute_gaussian(r, img_w, img_h,
                     gaussian_w, gaussian_h,
                     gaussian_cx, gaussian_cy):
    for y in range(img_h):
        for x in range(img_w):
            ds = ((gaussian_cx-x)/gaussian_w)**2
            ds += ((gaussian_cy-y)/gaussian_h)**2
            r[x, y] = np.exp(-ds/2)


def fit(data, get_dataset):
    img_w, img_h = data.shape

    def err(parameters):
        r = np.empty((img_w, img_h))
        compute_gaussian(r, img_w, img_h, *parameters)
        r -= data
        return r.ravel()
    guess = [
        get_dataset("rexec_demo.gaussian_w", 12),
        get_dataset("rexec_demo.gaussian_h", 15),
        get_dataset("rexec_demo.gaussian_cx", img_w/2),
        get_dataset("rexec_demo.gaussian_cy", img_h/2)
    ]
    res = least_squares(err, guess)
    return res.x


def get_and_fit():
    if "dataset_db" in globals():
        logger.info("using dataset DB for Gaussian fit guess")

        def get_dataset(name, default):
            try:
                return dataset_db.get(name)
            except KeyError:
                return default
    else:
        logger.info("using defaults for Gaussian fit guess")

        def get_dataset(name, default):
            return default
    return fit(controller_driver.get_picture(), get_dataset)
