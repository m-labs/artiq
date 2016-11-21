from artiq.language import *


frame_setup = 20*ns
trigger_duration = 50*ns
sample_period = 10*ns
delay_margin_factor = 1 + 1e-4


class FrameActiveError(Exception):
    """Raised when a frame is active and playback of a segment from another
    frame is attempted."""
    pass


class SegmentSequenceError(Exception):
    """Raised when attempting to play back a named segment which is not the
    next in the sequence."""
    pass


class InvalidatedError(Exception):
    """Raised when attemting to use a frame or segment that has been
    invalidated (due to disarming the PDQ)."""
    pass


class ArmError(Exception):
    """Raised when attempting to arm an already armed PDQ, to modify the
    program of an armed PDQ, or to play a segment on a disarmed PDQ."""
    pass


class _Segment:
    def __init__(self, frame, segment_number):
        self.frame = frame
        self.segment_number = segment_number

        self.lines = []
        self.duration = 0*s

        # for @kernel
        self.core = frame.pdq.core

    def add_line(self, duration, channel_data, dac_divider=1):
        if self.frame.invalidated:
            raise InvalidatedError()
        if self.frame.pdq.armed:
            raise ArmError()
        self.lines.append((dac_divider, duration, channel_data))
        self.duration += duration*sample_period/dac_divider

    def get_duration(self):
        return self.duration

    @kernel
    def advance(self):
        if self.frame.invalidated:
            raise InvalidatedError()
        if not self.frame.pdq.armed:
            raise ArmError()
        # If a frame is currently being played, check that we are next.
        if (self.frame.pdq.current_frame >= 0 and
                self.frame.pdq.next_segment != self.segment_number):
            raise SegmentSequenceError()
        self.frame.advance()


class _Frame:
    def __init__(self, pdq, frame_number):
        self.pdq = pdq
        self.frame_number = frame_number
        self.segments = []
        self.segment_count = 0  # == len(self.segments), used in kernel

        self.invalidated = False

        # for @kernel
        self.core = self.pdq.core

    def create_segment(self, name=None):
        if self.invalidated:
            raise InvalidatedError()
        if self.pdq.armed:
            raise ArmError()
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
            self.core.seconds_to_mu(s.duration*delay_margin_factor)
            for s in self.segments]

    def _invalidate(self):
        self.invalidated = True

    def _get_program(self):
        r = []
        for segment in self.segments:
            if segment.duration < 2*trigger_duration:
                raise ValueError(("Segment too short ({:g} s), trigger might "
                                  "spill").format(segment.duration))
            segment_program = [
                {
                    "dac_divider": dac_divider,
                    "duration": duration,
                    "channel_data": channel_data,
                    "trigger": False,
                } for dac_divider, duration, channel_data in segment.lines]
            segment_program[0]["trigger"] = True
            r += segment_program
        return r

    @kernel
    def advance(self):
        if self.invalidated:
            raise InvalidatedError()
        if not self.pdq.armed:
            raise ArmError()

        call_t = now_mu()
        trigger_start_t = call_t - self.core.seconds_to_mu(trigger_duration/2)

        if self.pdq.current_frame >= 0:
            # PDQ is in the middle of a frame. Check it is us.
            if self.pdq.current_frame != self.frame_number:
                raise FrameActiveError()
        else:
            # PDQ is in the jump table - set the selection signals
            # to play our first segment.
            self.pdq.current_frame = self.frame_number
            self.pdq.next_segment = 0
            at_mu(trigger_start_t - self.core.seconds_to_mu(frame_setup))
            self.pdq.frame0.set_o(bool(self.frame_number & 1))
            self.pdq.frame1.set_o(bool((self.frame_number & 2) >> 1))
            self.pdq.frame2.set_o(bool((self.frame_number & 4) >> 2))

        at_mu(trigger_start_t)
        self.pdq.trigger.pulse(trigger_duration)

        at_mu(call_t)
        delay_mu(self.segment_delays[self.pdq.next_segment])
        self.pdq.next_segment += 1

        # test for end of frame
        if self.pdq.next_segment == self.segment_count:
            self.pdq.current_frame = -1
            self.pdq.next_segment = -1


class CompoundPDQ2:
    def __init__(self, dmgr, pdq2_devices, trigger_device, frame_devices):
        self.core = dmgr.get("core")
        self.pdq2s = [dmgr.get(d) for d in pdq2_devices]
        self.trigger = dmgr.get(trigger_device)
        self.frame0 = dmgr.get(frame_devices[0])
        self.frame1 = dmgr.get(frame_devices[1])
        self.frame2 = dmgr.get(frame_devices[2])

        self.frames = []
        self.current_frame = -1
        self.next_segment = -1
        self.armed = False

    def disarm(self):
        for frame in self.frames:
            frame._invalidate()
        self.frames.clear()
        for dev in self.pdq2s:
            dev.park()
        self.armed = False

    def get_program(self):
        return [f._get_program() for f in self.frames]

    def arm(self):
        if self.armed:
            raise ArmError()
        for frame in self.frames:
            frame._arm()

        full_program = self.get_program()
        n = 0
        for pdq2 in self.pdq2s:
            dn = pdq2.get_num_channels()
            program = []
            for full_frame_program in full_program:
                frame_program = []
                for full_line in full_frame_program:
                    line = {
                        "dac_divider": full_line["dac_divider"],
                        "duration": full_line["duration"],
                        "channel_data": full_line["channel_data"][n:n + dn],
                        "trigger": full_line["trigger"],
                    }
                    frame_program.append(line)
                program.append(frame_program)
            pdq2.program(program)
            n += dn
        for pdq2 in self.pdq2s:
            pdq2.unpark()
        self.armed = True

    def create_frame(self):
        if self.armed:
            raise ArmError()
        r = _Frame(self, len(self.frames))
        self.frames.append(r)
        return r
