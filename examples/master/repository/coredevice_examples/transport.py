# Copyright (C) 2014, 2015 Robert Jordens <jordens@gmail.com>

import numpy as np

from artiq.language import *

from artiq.wavesynth.coefficients import SplineSource

transport = SplineSource(
    x=np.linspace(0, 10, 101),  # waveform time
    y=np.random.rand(4*3*3, 101)*1e-6,  # waveform data,
    # 4 devices, 3 board each, 3 dacs each
)

class Transport(EnvExperiment):
    """Transport"""

    def build(self):
        self.core = self.get_device("core")
        self.bd_sw = self.get_device("bd_sw")
        self.pmt = self.get_device("pmt")
        self.electrodes = self.get_device("electrodes")

        self.wait_at_stop = self.get_argument("wait_at_stop",
                                              NumberValue(100*us))
        self.speed = self.get_argument("speed", NumberValue(1.5))
        self.repeats = self.get_argument("repeats", NumberValue(100))
        self.nbins = self.get_argument("nbins", NumberValue(100))

    def calc_waveforms(self, stop):
        self.electrodes.disarm()
        self.tf = self.electrodes.create_frame()
        to_stop = self.tf.create_segment("to_stop")
        from_stop = self.tf.create_segment("from_stop")
        transport.extend_segment(to_stop, 0, stop, scale=self.speed)
        # append the reverse transport (from stop to 0)
        # both durations are the same in this case
        transport.extend_segment(from_stop, 0, stop, scale=self.speed)
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
        with parallel:
            self.bd_sw.pulse(100*us)
            self.pmt.gate_rising(100*us)
        self.bd_sw.on()
        return self.pmt.count()

    @kernel
    def one(self):
        self.cool()
        self.transport()
        return self.detect()

    @kernel
    def repeat(self):
        self.histogram[:] = [0 for _ in range(self.nbins)]

        for i in range(self.repeats):
            n = self.one()
            if n >= self.nbins:
                n = self.nbins - 1
            self.histogram[n] += 1

    def scan(self, stops):
        for s in stops:
            self.histogram = []
            # non-kernel, build frames
            # could also be rpc'ed from repeat()
            self.calc_waveforms(s)
            # kernel part
            self.repeat()
            # live update 2d plot with current self.histogram
            # broadcast(s, self.histogram)

    def run(self):
        # scan transport endpoint
        stops = range(10, len(transport.x), 10)
        self.scan(stops)
