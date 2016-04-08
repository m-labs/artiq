import io

import numpy as np
import matplotlib.pyplot as plt

from artiq.experiment import *


class Thumbnail(EnvExperiment):
    def build(self):
        pass

    def run(self):
        pass

    def analyze(self):
        plt.plot([1, 2, 0, 3, 4])
        f = io.BytesIO()
        plt.savefig(f, format="PNG")
        f.seek(0)
        self.set_dataset("thumbnail", np.void(f.read()))
