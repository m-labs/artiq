#!/usr/bin/env python3

import numpy as np
from numba import jit
import logging

from sipyco.remote_exec import simple_rexec_server_loop


@jit(nopython=True)
def compute_picture(r, img_w, img_h,
                    gaussian_w, gaussian_h,
                    gaussian_cx, gaussian_cy,
                    noise_level):
    for y in range(img_h):
        for x in range(img_w):
            ds = ((gaussian_cx-x)/gaussian_w)**2 
            ds += ((gaussian_cy-y)/gaussian_h)**2
            r[x, y] = np.exp(-ds/2) + noise_level*np.random.random()


class CameraSimulation:
    def __init__(self):
        self.img_w = 320
        self.img_h = 200
        self.gaussian_w = 4
        self.gaussian_h = 3
        self.gaussian_cx = self.img_w//2
        self.gaussian_cy = self.img_h//2
        self.noise_level = 0.1

    def set_gaussian_width(self, wx, wy=None):
        if wy is None:
            wy = wx
        self.gaussian_w = wx
        self.gaussian_h = wy

    def set_gaussian_center(self, x, y):
        self.gaussian_cx = x
        self.gaussian_cy = y

    def set_noise_level(self, noise_level):
        self.noise_level = noise_level

    def get_picture(self):
        r = np.empty((self.img_w, self.img_h))
        compute_picture(r, self.img_w, self.img_h,
            self.gaussian_w, self.gaussian_h,
            self.gaussian_cx, self.gaussian_cy,
            self.noise_level)
        return r

    def ping(self):
        return True


def main():
    logging.basicConfig(level=logging.INFO)
    simple_rexec_server_loop("camera_sim", CameraSimulation(),
                             "::1", 6283)

if __name__ == "__main__":
    main()
