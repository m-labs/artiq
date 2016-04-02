"""Image processing with SciPy example"""

import numpy as np
from scipy.optimize import least_squares
from scipy import constants


class Fit:
    variables = []  # fixed ordering

    def build(self, data, meta):
        self.data = data
        self.meta = meta

    def variables_dict(self, param):
        return dict(zip(self.variables, param))

    def guess(self):
        raise NotImplementedError

    def model(self, *param, **kwargs):
        raise NotImplementedError

    def fit(self, *param, **kwargs):
        def fun(x, *args, **kwargs):
            return (self.model(x, *args, **kwargs) - self.data).ravel()

        try:
            mjac = self.model_jacobian

            def jac(x, *args, **kwargs):
                return mjac(x, *args, **kwargs).reshape(-1, x.size)
        except AttributeError:
            jac = "2-point"

        res = least_squares(fun, param, jac, **kwargs)
        _, s, v = np.linalg.svd(res.jac, full_matrices=False)
        threshold = np.finfo(float).eps * max(res.jac.shape) * s[0]
        s = s[s > threshold]
        v = v[:s.size]
        pcov = np.dot(v.T/s**2, v)
        return res.x, pcov

    def process(self, cov, *param):
        return self.variables_dict(param)

    def run(self, data, meta, **kwargs):
        self.build(data, meta)
        param = self.guess()
        param, cov = self.fit(*param, **kwargs)
        results = self.process(cov, *param)
        return param, results


def od_to_n(od, meta):
    return (od*meta["pitch_x"]*meta["pitch_x"] *
            (1.+4.*meta["detuning"]**2)/meta["sigma0"])


def area_gauss(p, h, w):
    return 2.*np.pi*p*abs(w*h)


def area_parabola(p, h, w):
    return p*2/5.*np.pi/abs(w*h)**.5


def t_gauss(mass, omega, width, tof):
    return mass/constants.Boltzmann*(omega*width)**2/(1. + (tof*omega)**2)


class Fit2DGaussParabola(Fit):
    variables = ["i_offset", "x_center", "y_center",
                 "a_parabola", "v_parabola", "w_parabola",
                 "a_gauss", "v_gauss", "w_gauss"]

    def build(self, data, meta):
        super(Fit2DGaussParabola, self).build(data, meta)
        self.xy = np.ogrid[:data.shape[0], :data.shape[1]]

    def guess(self):
        # TODO: this is usually smarter, based on self.data and self.meta
        return [1000, 100, 100, 2000, 4, 4, 2000, 20, 20]

    def model(self, param):
        p = self.variables_dict(param)
        x, y = self.xy
        x2 = (x - p["x_center"])**2
        y2 = (y - p["y_center"])**2
        gauss = p["a_gauss"]*np.exp(
            -(x2/p["v_gauss"]**2 + y2/p["w_gauss"]**2)/2)
        r = 1 - p["v_parabola"]*x2 - p["w_parabola"]*y2
        parabola = p["a_parabola"]*np.where(r > 0, r, 0)**1.5
        return p["i_offset"] + gauss + parabola

    def process(self, cov, *param):
        r = self.variables_dict(param)
        r["cov"] = np.diag(cov)
        # TODO: handle cov, compute confidence intervals
        r["n_condensate"] = area_parabola(od_to_n(r["a_parabola"], self.meta),
                                          r["v_parabola"], r["w_parabola"])
        r["n_thermal"] = area_gauss(od_to_n(r["a_gauss"], self.meta),
                                    r["v_gauss"], r["w_gauss"])
        r["t_x"] = t_gauss(self.meta["mass"], self.meta["omega_x"],
                           r["v_gauss"]*self.meta["pitch_x"], self.meta["tof"])
        r["t_y"] = t_gauss(self.meta["mass"], self.meta["omega_y"],
                           r["w_gauss"]*self.meta["pitch_y"], self.meta["tof"])
        r["t"] = (r["t_x"] + r["t_y"])/2
        return r


if __name__ == "__main__":
    # generate some test data
    f = Fit2DGaussParabola()
    f.xy = np.ogrid[:300, :300]
    i = f.model(f.guess())
    # make it noisy
    i += 100 + np.random.randn(*i.shape)*200 + i*np.random.randn(*i.shape)*.1
    meta = dict(mass=constants.atomic_mass*87, tof=25e-3,
                omega_x=2*np.pi*30, omega_y=2*np.pi*100,
                pitch_x=2e-6, pitch_y=2e-6,
                detuning=0, sigma0=1e-12)

    # fit it
    f = Fit2DGaussParabola()
    p, r = f.run(i, meta)
    print(r)

    from timeit import timeit
    print(timeit("f.model(p)", globals=globals(), number=10))

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 2)
    for axi, ii in zip(ax.ravel(),
                       (i, f.model(f.guess()),
                        f.model(p), (f.model(p) - i) + 1000)):
        axi.imshow(ii, cmap=plt.cm.Greys, vmin=0, vmax=5000)
    plt.show()
