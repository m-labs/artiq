import unittest

import numpy as np

from artiq.wavesynth import coefficients, compute_samples


class TestSplineCoef(unittest.TestCase):
    def setUp(self):
        self.x = np.arange(5.)
        self.y = np.sin(2*np.pi*self.x/5) + np.arange(2)[:, None]
        self.s = coefficients.SplineSource(self.x, self.y, order=4)

    def test_get_segment(self):
        return list(self.s.get_segment_data(start=1.5, stop=3.2, scale=.01))

    def test_synth(self):
        d = self.test_get_segment()
        d[0]["trigger"] = True
        return compute_samples.Synthesizer(self.y.shape[0], [d, d + d])

    def drive(self, s):
        y = []
        for f in 0, 1, None, 0:
            if f is not None:
                s.select(f)
            y += s.trigger()[0]
        return y

    def test_run(self):
        return self.drive(self.test_synth())

    @unittest.skip("manual/visual test")
    def test_plot(self):
        import matplotlib.pyplot as plt
        y = self.test_run()
        plt.step(np.arange(len(y)), y)
        plt.show()
