import numpy as np

from artiq.language.core import *
from artiq.language.units import *
from artiq.wavesynth.compute_samples import Synthesizer


class SegmentSequenceError(Exception):
    """Raised when attempting to play back a named segment which is not the
    next in the sequence."""
    pass


class InvalidatedError(Exception):
    """Raised when attemting to use a frame or segment that has been
    invalidated (due to disarming the DAQmx)."""
    pass


class ArmError(Exception):
    """Raised when attempting to arm an already armed DAQmx, to modify the
    program of an armed DAQmx, or to play a segment on a disarmed DAQmx."""
    pass


def _ceil_div(a, b):
    return (a + b - 1)//b


def _compute_duration_mu(nsamples, ftw, acc_width):
    # This returns the precise duration so that the clock can be stopped
    # exactly at the next rising edge (RTLink commands take precedence over
    # toggling from the accumulator).
    # If segments are played continuously, replacement of the stop command
    # will keep the clock running. If the FTW is not a power of two, note that
    # the accumulator is reset at that time, which causes jitter and frequency
    # inaccuracy.
    # Formally:
    #    duration     *ftw >= nsamples*2**acc_width
    #   (duration - 1)*ftw <  nsamples*2**acc_width 
    return _ceil_div(nsamples*2**acc_width, ftw)


class _Segment:
    def __init__(self, frame, segment_number):
        self.frame = frame
        self.segment_number = segment_number

        self.lines = []

        # for @kernel
        self.core = frame.daqmx.core

    def add_line(self, duration, channel_data):
        if self.frame.invalidated:
            raise InvalidatedError
        if self.frame.daqmx.armed:
            raise ArmError
        self.lines.append((duration, channel_data))

    @kernel
    def advance(self):
        if self.frame.invalidated:
            raise InvalidatedError
        if not self.frame.daqmx.armed:
            raise ArmError
        # If the frame is currently being played, check that we are next.
        if (self.frame.daqmx.next_segment >= 0
                and self.frame.daqmx.next_segment != self.segment_number):
            raise SegmentSequenceError
        self.frame.advance()


class _Frame:
    def __init__(self, daqmx):
        self.daqmx = daqmx
        self.segments = []
        self.segment_count = 0  # == len(self.segments), used in kernel

        self.invalidated = False

        # for @kernel
        self.core = self.daqmx.core

    def create_segment(self, name=None):
        if self.invalidated:
            raise InvalidatedError
        if self.daqmx.armed:
            raise ArmError
        segment = _Segment(self, self.segment_count)
        if name is not None:
            if hasattr(self, name):
                raise NameError("Segment name already exists")
            setattr(self, name, segment)
        self.segments.append(segment)
        self.segment_count += 1
        return segment

    def _arm(self):
        self.segment_delays = [
            _compute_duration_mu(s.get_sample_count(),
                                 self.daqmx.sample_rate,
                                 self.daqmx.clock.acc_width)
            for s in self.segments]

    def _invalidate(self):
        self.invalidated = True

    def _get_samples(self):
        program = [
            {
                "dac_divider": 1,
                "duration": duration,
                "channel_data": channel_data,
            } for duration, channel_data in segment.lines 
                for segment in self.segments]
        synth = Synthesizer(self.daqmx.channel_count, program)
        synth.select(0)
        # not setting any trigger flag in the program causes the whole
        # waveform to be computed here for all segments.
        # slicing the segments is done by stopping the clock.
        return synth.trigger()

    @kernel
    def advance(self):
        if self.invalidated:
            raise InvalidatedError
        if not self.daqmx.armed:
            raise ArmError

        self.daqmx.clock.set(self.daqmx.sample_rate)
        delay_mu(self.segment_delays[self.daqmx.next_segment])
        self.daqmx.next_segment += 1
        self.daqmx.clock.stop()

        # test for end of frame
        if self.daqmx.next_segment == self.segment_count:
            self.daqmx.next_segment = -1


class CompoundDAQmx:
    def __init__(self, dmgr, daqmx_device, clock_device, channel_count,
                 sample_rate, sample_rate_in_mu=False):
        self.core = dmgr.get("core")
        self.daqmx = dmgr.get(daqmx_device)
        self.clock = dmgr.get(clock_device)
        self.channel_count = channel_count
        if self.sample_rate_in_mu:
            self.sample_rate = sample_rate
        else:
            self.sample_rate = self.clock.frequency_to_ftw(sample_rate)

        self.frame = None
        self.next_segment = -1
        self.armed = False

    def disarm(self):
        if self.frame is not None:
            self.frame._invalidate()
        self.frame = None
        self.armed = False

    def arm(self):
        if self.armed:
            raise ArmError
        if self.frame is not None:
            self.frame._arm()
            self.daqmx.load_sample_values(
                self.clock.ftw_to_frequency(self.sample_rate),
                np.array(self.frame._get_samples()))
        self.armed = True

    def create_frame(self):
        if self.armed:
            raise ArmError
        self.frame = _Frame(self)
        return self.frame
