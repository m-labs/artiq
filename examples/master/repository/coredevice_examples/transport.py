# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import numpy as np

from artiq.experiment import *
from artiq.wavesynth.coefficients import SplineSource


class Transport(EnvExperiment):
    """Transport"""

    def build(self):
        self.setattr_device("core")
        self.setattr_device("bd_sw")
        self.setattr_device("pmt")
        self.setattr_device("electrodes")

        self.setattr_argument("wait_at_stop", NumberValue(100*us))
        self.setattr_argument("speed", NumberValue(1/(10*us)))
        self.setattr_argument("repeats", NumberValue(100))
        self.setattr_argument("bins", NumberValue(100))

        t = np.linspace(0, 10, 101)  # waveform time
        u = 1 - np.cos(np.pi*t/t[-1])
        # 4 devices, 3 board each, 3 dacs each
        u = np.arange(4*3*3)[:, None]*.1 + u
        self.data = SplineSource(x=t, y=u)

    def calc_waveforms(self, stop):
        scale = self.speed/(50*MHz)
        self.electrodes.disarm()
        self.tf = self.electrodes.create_frame()
        self.data.extend_segment(self.tf.create_segment("to_stop"),
                                 0, stop, scale=scale)
        # append the reverse transport (from stop to 0)
        # both durations are the same in this case
        self.data.extend_segment(self.tf.create_segment("from_stop"),
                                 stop, 0, scale=scale)
        # distributes frames to the sub-devices in CompoundPDQ2
        # and uploads them
        self.electrodes.arm()

    @kernel
    def cool(self):
        self.bd_sw.pulse(1*ms)

    @kernel
    def transport(self):
        # selects transport frame
        # triggers pdqs to start transport frame segment
        # plays the transport waveform from 0 to stop
        # delay()s the core by the duration of the waveform segment
        self.tf.to_stop.advance()
        # leaves the ion in the dark at the transport endpoint
        delay(self.wait_at_stop)
        # transport back (again: trigger, delay())
        # segments can only be advance()ed in order
        # since this is the last segment, pdq will go back to jump table
        self.tf.from_stop.advance()

    @kernel
    def detect(self):
        self.bd_sw.on()
        self.pmt.gate_rising(100*us)
        return self.pmt.count()

    @kernel
    def one(self):
        self.cool()
        self.transport()
        return self.detect()

    @kernel
    def repeat(self):
        hist = [0 for _ in range(self.bins)]
        for i in range(self.repeats):
            n = self.one()
            if n >= self.bins:
                n = self.bins - 1
            hist[n] += 1
        self.set_dataset("hist", hist)

    def scan(self, stops):
        for s in stops:
            self.histogram = [0 for _ in range(self.bins)]
            # non-kernel, build frames
            # could also be rpc'ed from repeat()
            self.calc_waveforms(s)
            # kernel part
            self.repeat()

    def run(self):
        # scan transport endpoint
        stops = np.linspace(0, 10, 10)
        self.scan(stops)


# class Benchmark(Transport):
#     def build(self):
#         Transport.build(self)
#         self.calc_waveforms(.3)
#
#     @kernel
#     def run(self):
#         self.repeat()
