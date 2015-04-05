import numpy as np
from scipy.interpolate import splrep, splev


def _round_times(times, sample_times=None):
    times = np.asanyarray(times)
    if sample_times is None:
        sample_times = np.rint(times)
    duration = np.diff(sample_times)
    sample_times = sample_times[:-1]
    assert np.all(duration >= 0)
    assert np.all(duration < (1 << 16))
    return times, sample_times, duration


def _interpolate(time, data, sample_times, order=3):
    # FIXME: this does not ensure that the spline does not clip
    spline = splrep(time, data, k=order or 1)
    # FIXME: this could be faster but needs k knots outside t_eval
    # dv = np.array(spalde(t_eval, s))
    coeffs = np.array([splev(sample_times, spline, der=i, ext=0)
                       for i in range(order + 1)]).T
    return coeffs


def discrete_compensate(c):
    l = len(c)
    if l > 2:
        c[1] += c[2]/2.
    if l > 3:
        c[1] += c[3]/6.
        c[2] += c[3]
    if l > 4:
        raise ValueError("only third-order splines supported")


def _zip_program(times, channels, target):
    for tc in zip(times, *channels):
        yield {
            "duration": tc[0],
            "channel_data": tc[1:],
        }
# FIXME: this does not handle:
# `clear` (clearing the phase accumulator)
# `silence` (stopping the dac clock)


def interpolate_channels(times, data, sample_times=None, **kwargs):
    if len(times) == 1:
        return _zip_program(np.array([1]), data[:, :, None])
    data = np.asanyarray(data)
    assert len(times) == len(data)
    times, sample_times, duration = _round_times(times, sample_times)
    channel_coeff = [_interpolate(sample_times, i, **kwargs) for i in data.T]
    return _zip_program(duration, np.array(channel_coeff))
    # v = np.clip(v/self.max_out, -1, 1)
