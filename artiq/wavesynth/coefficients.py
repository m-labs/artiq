import numpy as np
from scipy.interpolate import splrep, splev, spalde
from scipy.special import binom


class UnivariateMultiSpline:
    """Multidimensional wrapper around `scipy.interpolate.sp*` functions.
    `scipy.inteprolate.splprep` unfortunately does only up to 12 dimsions.
    """
    def __init__(self, x, y, order=4):
        self.order = order
        self.s = [splrep(x, yi, k=order - 1) for yi in y]

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


class UnivariateMultiSparseSpline(UnivariateMultiSpline):
    def __init__(self, d, x0=None, order=4):
        self.order = order
        self.n = sorted(set(n for x, n, y in d))
        self.s = []
        for n in self.n:
            x, y = np.array([(x, y) for x, ni, y in d if n == ni]).T
            if x0 is not None:
                y0 = splev(x0, splrep(x, y, k=order - 1))
                x, y = x0, y0
            s = splrep(x, y, k=order - 1)
            self.s.append(s)


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
                  variable="amplitude"):
    """Build a wavesynth-style segment from homogeneous duration and
    coefficient data.

    :param durations: 1D sequence of line durations.
    :param coefficients: 3D array with shape `(n, m, len(x))`,
        with `n` being the interpolation order + 1 and `m` the number of
        channels.
    :param target: The target component of the channel to affect.
    :param variable: The variable within the target component.
    """
    for dxi, yi in zip(durations, coefficients.transpose()):
        d = {"duration": int(dxi)}
        d["channel_data"] = cd = []
        for yij in yi:
            cdj = []
            for yijk in reversed(yij):
                if cdj or abs(yijk):
                    cdj.append(float(yijk))
            cdj.reverse()
            cd.append({target: {variable: cdj}})
        yield d


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

    def get_segment_data(self, start, stop, scale, cutoff=1e-12,
                         target="bias", variable="amplitude"):
        """Build wavesynth segment data.

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
        return build_segment(durations, coefficients, target=target,
                             variable=variable)

    def extend_segment(self, segment, trigger=True, *args, **kwargs):
        """Extend a wavesynth segment.

        See `get_segment()` for arguments.
        """
        for i, line in enumerate(self.get_segment_data(*args, **kwargs)):
            if i == 0:
                line["trigger"] = True
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
        self.spline = UnivariateMultiSpline(self.x, self.y, order)

    def crop_x(self, start, stop):
        ia, ib = np.searchsorted(self.x, (start, stop))
        if start > stop:
            x = self.x[ia - 1:ib - 1:-1]
        else:
            x = self.x[ia:ib]
        return np.r_[start, x, stop]

    def scale_x(self, x, scale, min_duration=1, min_length=20):
        """
        Due to minimum duration and/or minimum segment length constraints
        this method may drop samples from `x_sample` or adjust `durations` to
        comply. But `x_sample` and `durations` should be kept consistent.

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
        dt = dt[valid]
        t = t[np.r_[True, valid]]
        if dt.shape[0] == 1:
            dt[0] = max(dt[0], min_length)
        x_sample = t[:-1]*scale
        return x_sample, dt

    def __call__(self, x):
        return self.spline(x)


class ComposingSplineSource(SplineSource):
    # TODO: verify, test, document
    def __init__(self, x, y, components, order=4, pad_dx=1.):
        self.x = np.asanyarray(x)
        assert self.x.ndim == 1
        self.y = np.asanyarray(y)
        assert self.y.ndim == 3

        if pad_dx is not None:
            a = np.arange(-order, 0)*pad_dx + self.x[0]
            b = self.x[-1] + np.arange(1, order + 1)*pad_dx
            self.x = np.r_[a, self.x, b]
            self.y = pad_const(self.y, order, axis=2)

        assert self.y.shape[2] == self.x.shape[0]
        self.splines = [UnivariateMultiSpline(self.x, yi, order)
                        for yi in self.y]

        # need to resample/upsample the shim splines to the master spline knots
        # shim knot spacings can span an master spline knot and thus would
        # cross a highest order derivative boundary
        self.components = UnivariateMultiSparseSpline(
            components, self.x, order)

    def __call__(self, t, gain={}, offset={}):
        der = list((set(self.components.n) | set(offset))
                   & set(range(len(self.splines))))
        u = np.zeros((self.splines[0].order, len(self.splines[0].s), len(t)))
        # der, order, ele, t
        p = np.array([self.splines[i](t) for i in der])
        s_gain = np.array([gain.get(_, 1.) for _ in self.components.n])
        # order, der, None, t
        s = self.components(t)[:, :, None, :]*s_gain[None, :, None, None]
        for k, v in offset.items():
            if v:
                u += v*p[k]
        ps = p[self.shims.n]
        for i in range(u.shape[1]):
            for j in range(i + 1):
                u[i] += binom(i, j)*(s[j]*ps[:, i - j]).sum(0)
        return u  # (order, ele, t)


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
