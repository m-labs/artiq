from math import sqrt, cos, pi
import time

from artiq import *


def model(x, F0=1500, A=80, B=40, t=0.02, tpi=0.03):
    return A+(B-A)/2/(4*tpi**2*(x-F0)**2+1)*(1-cos(pi*t/tpi*sqrt(4*tpi**2*(x-F0)**2+1)))


class FloppingF(AutoDB):
    class DBKeys:
        implicit_core = False

        npoints = Argument(100)
        min_freq = Argument(1000)
        max_freq = Argument(2000)

        frequency = Result()
        brightness = Result()

        flopping_freq = Parameter()

    @staticmethod
    def realtime_results():
        return {
            ("frequency", "brightness"): "xy"
        }

    def run(self):
        for i in range(self.npoints):
            frequency = (self.max_freq-self.min_freq)*i/(self.npoints - 1) + self.min_freq
            brightness = model(frequency)
            self.frequency.append(frequency)
            self.brightness.append(brightness)
            time.sleep(0.1)
        self.analyze()

    def analyze(self):
        min_f = self.frequency.read[0]
        min_b = self.brightness.read[0]
        for f, b in zip(self.frequency.read, self.brightness.read):
            if b < min_b:
                min_f, min_b = f, b
        self.flopping_freq = min_f
