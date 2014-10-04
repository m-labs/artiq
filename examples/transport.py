import numpy as np

from artiq import *
from artiq.devices import corecom_serial, core, dds_core, rtio_core, pdq2


class Transport(AutoContext):
    parameters = ("bd pmt repeats nbins "
            "electrodes transport_data wait_at_stop speed"
    )
 
    def prepare(self, stop):
        t = self.data["t"][:stop]*self.speed
        u = self.data["u"][:stop]
        # start a new frame, selects possible frame id based on rtio_frame
        # assignments from coredev
        self.transport = self.electrodes.open_frame()
        # interpolates t and u and appends the (t, u) segment to the frame
        # adds wait-for-trigger to the first line/spline knot
        # will also apply offset and gain calibration data
        # stores duration and the fact that this segment needs to be triggered
        # both (duration and segment triggering flag) to be retrieved during
        # kernel compilation, see transport()
        self.transport.append(t, u, trigger=True)
        # append the reverse transport (from stop to 0)
        # both durations are the same in this case
        self.transport.append(t[-1] - t[::-1], u[::-1], trigger=True)
        # closes the frame with a wait line before jumping back into the jump table
        # so that frame signal can be set before the jump
        # also mark the frame as closed and prevent further append()ing
        self.transport.close()
        # packs all in-use frames, distributes them to the sub-devices in
        # CompoundPDQ2 and uploads them
        # uploading is ARM_DIS, writing, ARM_EN
        self.electrodes.prepare()

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
        # (it would be nice if this could be made zero-duration/not advancing the
        # timeline by smart scheduling of this frame-select + trigger + minimum wait
        # sequence)
        self.transport.begin()
        # triggers pdqs to start transport frame segment
        # plays the transport waveform from 0 to stop
        # delay()s the core by the duration of the waveform segment
        self.transport.advance()
        # leaves the ion in the dark at the transport endpoint
        delay(self.wait_at_stop)
        # transport back (again: trigger, delay())
        self.transport.advance()
        # ensures all segments have been advanced() through, must leave pdq
        # in a state where the next frame can begin()
        self.transport.finish()

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

    def report(self, i, n):
        self.histograms[i] = n
 
    @kernel
    def repeat(self):
        hist = array(0, self.nbins)

        for i in range(self.repeats):
            n = self.one()
            if n >= self.nbins:
                n = self.nbins-1
            hist[n] += 1

        for i in range(self.nbins):
            self.report(i, hist[i])

    def scan(self, stops):
        self.histograms = [0] * self.nbins
        for s in stops:
            # non-kernel, calculate waveforms, build frames
            # could also be rpc'ed from repeat()
            self.prepare(s)
            # kernel part
            self.repeat()
            # live update 2d plot with current self.histograms
            # self.broadcast(self.histograms)


if __name__ == "__main__":
    data = dict(
            t=np.linspace(0, 10, 101), # waveform time
            u=np.random.randn(101, 4*3*3), # waveform data,
            # 4 devices, 3 board each, 3 dacs each
    )
    # we would usually do
    # np.savez("transport.npz")

    with corecom_serial.CoreCom() as com:
        coredev = core.Core(com)
        exp = PhotonHistogram(
            core=coredev,
            bd=dds_core.DDS(core=coredev, dds_sysclk=1*GHz,
                            reg_channel=0, rtio_channel=1),
            pmt=rtio_core.RTIOIn(core=coredev, channel=0),
            # a compound pdq device that wraps multiple usb devices into one
            electrodes=pdq2.CompoundPDQ2(core=coredev,
                ids=["qc_q1_{}".format(i) for i in range(4)],
                rtio_trigger=3, rtio_frame=(4, 5, 6)),
            transport_data=data, # or: np.load("transport.npz")
            wait_at_stop=100*us,
            speed=1.5,
            repeats=100,
            nbins=100
        )
        # scan transport endpoint
        stop = range(exp.transport_data["t"].shape[0], 10)
        exp.scan(stop)
