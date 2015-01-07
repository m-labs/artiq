import numpy as np

from artiq import *


# data is usually precomputed offline
transport_data = dict(
    t=np.linspace(0, 10, 101),  # waveform time
    u=np.random.randn(101, 4*3*3),  # waveform data,
    # 4 devices, 3 board each, 3 dacs each
)

class Transport(AutoContext):
    bd = Device("dds")
    bdd = Device("dds")
    pmt = Device("ttl_in")
    electrodes = Device("pdq")

    wait_at_stop = Parameter(100*us)
    speed = Parameter(1.5)

    def prepare(self, stop):
        t = transport_data["t"][:stop]*self.speed
        u = transport_data["u"][:stop]
        # start a new frame
        self.tf = self.electrodes.create_frame()
        # interpolates t and u and appends the (t, u) segment to the frame
        # adds wait-for-trigger to the first line/spline knot
        # will also apply offset and gain calibration data
        # stores duration and the fact that this segment needs to be triggered
        # both (duration and segment triggering flag) to be retrieved during
        # kernel compilation, see transport()
        self.tf.append(t, u, trigger=True,
                       name="to_stop")
        # append the reverse transport (from stop to 0)
        # both durations are the same in this case
        self.tf.append(t[-1] - t[::-1], u[::-1], trigger=True,
                       name="from_stop")
        # closes the frame with a wait line before jumping back into
        # the jump table so that frame signal can be set before the jump
        # also mark the frame as closed and prevent further append()ing
        self.tf.close()
        # user must pass all frames that are going to be used next
        # selects possible frame id based on rtio_frame assignments
        # from core device
        # distributes frames to the sub-devices in CompoundPDQ2
        # and uploads them
        # uploading is ARM_DIS, writing, ARM_EN
        self.electrodes.prepare(self.tf)

    @kernel
    def cool(self):
        with parallel:
            self.bd.pulse(200*MHz, 1*ms)
            self.bdd.pulse(300*MHz, 1*ms)
        self.bd.pulse(210*MHz, 100*us)

    @kernel
    def transport(self):
        # ensures no frame is currently being actively played
        # set rtio frame select signal to frame id
        # rtio trigger jump into transport frame
        # (does not advance the timeline)
        self.tf.begin()
        # triggers pdqs to start transport frame segment
        # plays the transport waveform from 0 to stop
        # delay()s the core by the duration of the waveform segment
        self.tf.to_stop.advance()
        # leaves the ion in the dark at the transport endpoint
        delay(self.wait_at_stop)
        # transport back (again: trigger, delay())
        # segments can only be advance()ed in order
        self.tf.from_stop.advance()
        # ensures all segments have been advanced() through, must leave pdq
        # in a state where the next frame can begin()
        self.tf.finish()

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
    def repeat(self, repeats, nbins):
        self.histogram = [0 for _ in range(nbins)]

        for i in range(repeats):
            n = self.one()
            if n >= nbins:
                n = nbins - 1
            self.histogram[n] += 1

    def scan(self, repeats, nbins, stops):
        for s in stops:
            self.histogram = []
            # non-kernel, calculate waveforms, build frames
            # could also be rpc'ed from repeat()
            self.prepare(s)
            # kernel part
            self.repeat(repeats, nbins)
            # live update 2d plot with current self.histogram
            # broadcast(s, self.histogram)

    def run(self, repeats=100, nbins=100):
        # scan transport endpoint
        stops = range(10, len(transport_data["t"]), 10)
        self.scan(repeats, nbins, stops)
