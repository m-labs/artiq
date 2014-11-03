from artiq.language.core import *
from artiq.language.units import *
from artiq.coredevice import rtio


frame_setup = 20*ns
trigger_duration = 50*ns
frame_wait = 20*ns
sample_period = 10*us  # FIXME: check this


class SegmentSequenceError(Exception):
    pass


class FrameActiveError(Exception):
    pass


class FrameCloseError(Exception):
    pass


class _Segment:
    def __init__(self, frame, sn, duration, host_data):
        self.core = frame.core
        self.frame = frame
        self.sn = sn
        self.duration = duration
        self.host_data = host_data

    @kernel
    def advance(self):
        if self.frame.pdq.current_frame != self.frame.fn:
            raise FrameActiveError
        if self.frame.pdq.next_sn != self.sn:
            raise SegmentSequenceError
        self.frame.pdq.next_sn += 1

        t = time_to_cycles(now())
        self.frame.pdq.trigger.on(t)
        self.frame.pdq.trigger.off(t + time_to_cycles(trigger_duration))
        delay(self.duration)


class _Frame:
    def __init__(self, core):
        self.core = core
        self.segment_count = 0
        self.closed = False

    def append(self, t, u, trigger=False, name=None):
        if self.closed:
            raise FrameCloseError
        sn = self.segment_count
        duration = (t[-1] - t[0])*sample_period
        segment = _Segment(self, sn, duration, (t, u, trigger))
        if name is None:
            # TODO
            raise NotImplementedError("Anonymous segments are not supported yet")
        else:
            if hasattr(self, name):
                raise NameError("Segment name already exists")
            setattr(self, name, segment)
        self.segment_count += 1

    def close(self):
        if self.closed:
            raise FrameCloseError
        self.closed = True

    @kernel
    def begin(self):
        if self.pdq.current_frame >= 0:
            raise FrameActiveError
        self.pdq.current_frame = self.fn
        self.pdq.next_sn = 0

        t = (time_to_cycles(now())
            - time_to_cycles(frame_setup + trigger_duration + frame_wait))
        self.pdq.frame0.set_value(t, self.fn & 1)
        self.pdq.frame1.set_value(t, (self.fn & 2) >> 1)
        self.pdq.frame2.set_value(t, (self.fn & 4) >> 2)
        t += time_to_cycles(frame_setup)
        self.pdq.trigger.on(t)
        self.pdq.trigger.off(t + time_to_cycles(trigger_duration))

    @kernel
    def advance(self):
        # TODO
        raise NotImplementedError

    @kernel
    def finish(self):
        if self.pdq.current_frame != self.fn:
            raise FrameActiveError
        if self.pdq.next_sn != self.segment_count:
            raise FrameActiveError
        self.pdq.current_frame = -1
        self.pdq.next_sn = -1

    def _prepare(self, pdq, fn):
        if not self.closed:
            raise FrameCloseError
        self.pdq = pdq
        self.fn = fn

    def _invalidate(self):
        del self.pdq
        del self.fn


class CompoundPDQ2(AutoContext):
    parameters = "ids rtio_trigger rtio_frame"

    def build(self):
        self.trigger = rtio.LLRTIOOut(self, channel=self.rtio_trigger)
        self.frame0 = rtio.LLRTIOOut(self, channel=self.rtio_frame[0])
        self.frame1 = rtio.LLRTIOOut(self, channel=self.rtio_frame[1])
        self.frame2 = rtio.LLRTIOOut(self, channel=self.rtio_frame[2])

        self.frames = []
        self.current_frame = -1
        self.next_sn = -1

    def create_frame(self):
        return _Frame(self.core)

    def prepare(self, *frames):
        # prevent previous frames and their segments from
        # being (incorrectly) used again
        for frame in self.frames:
            frame._invalidate()

        self.frames = list(frames)
        for fn, frame in enumerate(frames):
            frame._prepare(self, fn)

        # TODO: upload to PDQ2 devices
