import numpy as np

from artiq import *


# data is usually precomputed offline
transport_data = dict(
    t=np.linspace(0, 10, 101),  # waveform time
    u=np.random.randn(101, 4*3*3),  # waveform data,
    # 4 devices, 3 board each, 3 dacs each
)

class Transport(EnvExperiment):
    """Transport"""

    def build(self):
        self.attr_device("core")
        self.attr_device("bd")
        self.attr_device("bdd")
        self.attr_device("pmt")
        self.attr_device("electrodes")

        self.attr_argument("wait_at_stop", FreeValue(100*us))
        self.attr_argument("speed", FreeValue(1.5))
        self.attr_argument("repeats", FreeValue(100))
        self.attr_argument("nbins", FreeValue(100))

    def calc_waveforms(self, stop):
        t = transport_data["t"][:stop]*self.speed
        u = transport_data["u"][:stop]

        self.electrodes.disarm()
        self.tf = self.electrodes.create_frame()
        self.tf.create_segment(t, u, name="to_stop")
        # append the reverse transport (from stop to 0)
        # both durations are the same in this case
        self.tf.create_segment(t[-1] - t[::-1], u[::-1], name="from_stop")
        # distributes frames to the sub-devices in CompoundPDQ2
        # and uploads them
        self.electrodes.arm()

    @kernel
    def cool(self):
        with parallel:
            self.bd.pulse(200*MHz, 1*ms)
            self.bdd.pulse(300*MHz, 1*ms)
        self.bd.pulse(210*MHz, 100*us)

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
            self.bd.pulse(220*MHz, 100*us)
            self.pmt.gate_rising(100*us)
        self.bd.on(200*MHz)
        self.bdd.on(300*MHz)
        return self.pmt.count()

    @kernel
    def one(self):
        self.cool()
        self.transport()
        return self.detect()

    @kernel
    def repeat(self):
        self.histogram = [0 for _ in range(self.nbins)]

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
        stops = range(10, len(transport_data["t"]), 10)
        self.scan(stops)
