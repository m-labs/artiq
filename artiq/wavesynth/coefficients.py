# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import numpy as np
from scipy.interpolate import splrep, splev, spalde


class UnivariateMultiSpline:
    """Multidimensional wrapper around `scipy.interpolate.sp*` functions.
    `scipy.inteprolate.splprep` is limited to 12 dimensions.
    """
    def __init__(self, x, y, *, x0=None, order=4, **kwargs):
        self.order = order
        self.x = x
        self.s = []
        for i, yi in enumerate(y):
            if x0 is not None:
                yi = self.upsample_knots(x0[i], yi, x)
            self.s.append(splrep(x, yi, k=order - 1, **kwargs))

    def upsample_knots(self, x0, y0, x):
        return splev(x, splrep(x0, y0, k=self.order - 1))

    def lev(self, x, *a, **k):
        return np.array([splev(x, si) for si in self.s])

    def alde(self, x):
        u = np.array([spalde(x, si) for si in self.s])
        if len(x) == 1:
            u = u[:, None, :]
        return u

    def __call__(self, x, use_alde=True):
        if use_alde:
            u = self.alde(x)[:, :, :self.order]
            s = (len(self.s), len(x), self.order)
            assert u.shape == s, (u.shape, s)
            return u.transpose(2, 0, 1)
        else:
            return np.array([self.lev(x, der=i) for i in range(self.order)])


def pad_const(x, n, axis=0):
    """Prefix and postfix the array `x` by `n` repetitions of the first and
    last value along `axis`.
    """
    a = np.repeat(x.take([0], axis), n, axis)
    b = np.repeat(x.take([-1], axis), n, axis)
    xp = np.concatenate([a, x, b], axis)
    s = list(x.shape)
    s[axis] += 2*n
    assert xp.shape == tuple(s), (x.shape, s, xp.shape)
    return xp


def build_segment(durations, coefficients, target="bias",
                  variable="amplitude", compress=True):
    """Build a wavesynth-style segment from homogeneous duration and
    coefficient data.

    :param durations: 1D sequence of line durations.
    :param coefficients: 3D array with shape `(n, m, len(durations))`,
        with `n` being the interpolation order + 1 and `m` the number of
        channels.
    :param target: The target component of the channel to affect.
    :param variable: The variable within the target component.
    :param compress: If `True`, skip zero high order coefficients.
    """
    for dxi, yi in zip(durations, coefficients.transpose()):
        cd = []
        for yij in yi:
            cdj = []
            for yijk in reversed(yij):
                if cdj or abs(yijk) or not compress:
                    cdj.append(float(yijk))
            cdj.reverse()
            if not cdj:
                cdj.append(float(yij[0]))
            cd.append({target: {variable: cdj}})
        yield {"duration": int(dxi), "channel_data": cd}


class CoefficientSource:
    def crop_x(self, start, stop, num=2):
        """Return an array of valid sample positions.

        This method needs to be overloaded if this `CoefficientSource`
        does not support sampling at arbitrary positions or at arbitrary
        density.

        :param start: First sample position.
        :param stop: Last sample position.
        :param num: Number of samples between `start` and `stop`.
        :return: Array of sample positions. `start` and `stop` should be
            returned as the first and last value in the array respectively.
        """
        return np.linspace(start, stop, num)

    def scale_x(self, x, scale):
        # TODO: This could be moved to the the Driver/Mediator code as it is
        # device-specific.
        """Scale and round sample positions.

        The sample times may need to be changed and/or decimated if
        incompatible with hardware requirements.

        :param x: Input sample positions in data space.
        :param scale: Data space position to cycles conversion scale,
            in units of x-units per clock cycle.
        :return: `x_sample`, the rounded sample positions and `durations`, the
            integer durations of the individual samples in cycles.
        """
        t = np.rint(x/scale)
        x_sample = t*scale
        durations = np.diff(t).astype(np.int)
        return x_sample, durations

    def __call__(self, x, **kwargs):
        """Perform sampling and return coefficients.

        :param x: Sample positions.
        :return: `y` the array of coefficients. `y.shape == (order, n, len(x))`
            with `n` being the number of channels."""
        raise NotImplementedError

    def get_segment(self, start, stop, scale, *, cutoff=1e-12,
                    target="bias", variable="amplitude"):
        """Build wavesynth segment.

        :param start: see `crop_x()`.
        :param stop: see `crop_x()`.
        :param scale: see `scale_x()`.
        :param cutoff: coefficient cutoff towards zero to compress data.
        """
        x = self.crop_x(start, stop)
        x_sample, durations = self.scale_x(x, scale)
        coefficients = self(x_sample)
        if len(x_sample) == 1 and start == stop:
            coefficients = coefficients[:1]
        # rescale coefficients accordingly
        coefficients *= (scale*np.sign(durations))**np.arange(
            coefficients.shape[0])[:, None, None]
        if cutoff:
            coefficients[np.fabs(coefficients) < cutoff] = 0
        return build_segment(np.fabs(durations), coefficients, target=target,
                             variable=variable)

    def extend_segment(self, segment, *args, **kwargs):
        """Extend a wavesynth segment.

        See `get_segment()` for arguments.
        """
        for line in self.get_segment(*args, **kwargs):
            segment.add_line(**line)


class SplineSource(CoefficientSource):
    def __init__(self, x, y, order=4, pad_dx=1.):
        """
        :param x: 1D sample positions.
        :param y: 2D sample values.
        """
        self.x = np.asanyarray(x)
        assert self.x.ndim == 1
        self.y = np.asanyarray(y)
        assert self.y.ndim == 2

        if pad_dx is not None:
            a = np.arange(-order, 0)*pad_dx + self.x[0]
            b = self.x[-1] + np.arange(1, order + 1)*pad_dx
            self.x = np.r_[a, self.x, b]
            self.y = pad_const(self.y, order, axis=1)

        assert self.y.shape[1] == self.x.shape[0]
        self.spline = UnivariateMultiSpline(self.x, self.y, order=order)

    def crop_x(self, start, stop):
        ia, ib = np.searchsorted(self.x, (start, stop))
        if start > stop:
            x = self.x[ia - 1:ib - 1:-1]
        else:
            x = self.x[ia:ib]
        return np.r_[start, x, stop]

    def scale_x(self, x, scale, min_duration=1, min_length=20):
        """Enforce, round, and scale x to device-dependent values.

        Due to minimum duration and/or minimum segment length constraints
        this method may drop samples from `x_sample` to comply.

        :param min_duration: Minimum duration of a line.
        :param min_length: Minimum segment length to space triggers.
        """
        # We want to only sample a spline at t_knot + epsilon
        # where the highest order derivative has just jumped
        # and is valid at least up to the next knot after t_knot.
        #
        # To ensure that we are on the correct side of a knot:
        # * only ever increase t when rounding (for increasing t)
        # * or only ever decrease it (for decreasing t)
        t = x/scale
        inc = np.diff(t) >= 0
        inc = np.r_[inc, inc[-1]]
        t = np.where(inc, np.ceil(t), np.floor(t))
        dt = np.diff(t.astype(np.int))

        valid = np.absolute(dt) >= min_duration
        if not np.any(valid):
            valid[0] = True
            dt[0] = max(dt[0], min_length)
        dt = dt[valid]
        x_sample = t[:-1][valid]*scale
        return x_sample, dt

    def __call__(self, x):
        return self.spline(x)


def discrete_compensate(c):
    """Compensate spline coefficients for discrete accumulators

    Given continuous-time b-spline coefficients, this function
    compensates for the effect of discrete time steps in the
    target devices.

    The compensation is performed in-place.
    """
    l = len(c)
    if l > 2:
        c[1] += c[2]/2.
    if l > 3:
        c[1] += c[3]/6.
        c[2] += c[3]
    if l > 4:
        raise ValueError("only third-order splines supported")
