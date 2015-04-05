# Robert Jordens <jordens@gmail.com>, 2012-2015

from math import log2, sqrt
import logging
import struct

import serial

from artiq.wavesynth.coefficients import discrete_compensate


logger = logging.getLogger(__name__)


class Segment:
    max_time = 1 << 16  # uint16 timer
    max_val = 1 << 15  # int16 DAC
    max_out = 10.  # Volt
    out_scale = max_val/max_out
    cordic_gain = 1.
    for i in range(16):
        cordic_gain *= sqrt(1 + 2**(-2*i))

    def __init__(self):
        self.data = b""

    def line(self, typ, duration, data, trigger=False, silence=False,
             aux=False, shift=0, jump=False, clear=False, wait=False):
        assert len(data) % 2 == 0, data
        assert len(data)//2 <= 14
        #assert dt*(1 << shift) > 1 + len(data)//2
        header = (
            1 + len(data)//2 | (typ << 4) | (trigger << 6) | (silence << 7) |
            (aux << 8) | (shift << 9) | (jump << 13) | (clear << 14) |
            (wait << 15)
        )
        self.data += struct.pack("<HH", header, duration) + data

    @staticmethod
    def pack(widths, values):
        fmt = "<"
        ud = []
        for width, value in zip(widths, values):
            value = int(round(value * (1 << 16*width)))
            if width == 2:
                ud.append(value & 0xffff)
                fmt += "H"
                value >>= 16
                width -= 1
            ud.append(value)
            fmt += "hi"[width]
        try:
            return struct.pack(fmt, *ud)
        except struct.error as e:
            logger.error("can not pack %s as %s (%s as %s): %s",
                         values, widths, ud, fmt, e)
            raise e

    def bias(self, amplitude=[], **kwargs):
        """Append a bias line to this segment.

        Amplitude in volts
        """
        coef = [self.out_scale*a for a in amplitude]
        discrete_compensate(coef)
        data = self.pack([0, 1, 2, 2], coef)
        self.line(typ=0, data=data, **kwargs)

    def dds(self, amplitude=[], phase=[], **kwargs):
        """Append a dds line to this segment.

        Amplitude in volts,
        phase[0] in turns,
        phase[1] in turns*sample_rate,
        phase[2] in turns*(sample_rate/2**shift)**2
        """
        scale = self.out_scale/self.cordic_gain
        coef = [scale*a for a in amplitude]
        discrete_compensate(coef)
        if phase:
            assert len(amplitude) == 4
        coef += [p*self.max_val*2 for p in phase]
        data = self.pack([0, 1, 2, 2, 0, 1, 1], coef)
        self.line(typ=1, data=data, **kwargs)


class Channel:
    num_frames = 8
    max_data = 4*(1 << 10)  # 8kx16 8kx16 4kx16

    def __init__(self):
        self.segments = []

    def clear(self):
        del self.segments[:]

    def new_segment(self):
        # assert len(self.segments) < self.num_frames
        segment = Segment()
        self.segments.append(segment)
        return segment

    def place(self):
        addr = self.num_frames
        for segment in self.segments:
            segment.addr = addr
            addr += len(segment.data)//2
        assert addr <= self.max_data, addr
        return addr

    def table(self, entry=None):
        table = [0] * self.num_frames
        if entry is None:
            entry = self.segments
        for i, frame in enumerate(entry):
            if frame is not None:
                table[i] = frame.addr
        return struct.pack("<" + "H"*self.num_frames, *table)

    def serialize(self, entry=None):
        self.place()
        data = b"".join([segment.data for segment in self.segments])
        return self.table(entry) + data


class Pdq2:
    """
    PDQ DAC (a.k.a. QC_Waveform)
    """
    num_dacs = 3

    _escape = b"\xa5"
    _commands = "RESET TRIGGER ARM DCM START".split()

    def __init__(self, url=None, dev=None, num_boards=3):
        if dev is None:
            dev = serial.serial_for_url(url)
        self.dev = dev
        self.num_boards = num_boards
        self.num_channels = self.num_dacs * self.num_boards
        self.channels = [Channel() for i in range(self.num_channels)]

    def close(self):
        self.dev.close()
        del self.dev

    def clear_all(self):
        for channel in self.channels:
            channel.clear()

    def write(self, data):
        logger.debug("> %r", data)
        written = self.dev.write(data)
        if isinstance(written, int):
            assert written == len(data)

    def cmd(self, cmd, enable):
        cmd = self._commands.index(cmd) << 1
        if not enable:
            cmd |= 1
        self.write(struct.pack("cb", self._escape, cmd))

    def write_mem(self, channel, data, start_addr=0):
        board, dac = divmod(channel, self.num_dacs)
        data = struct.pack("<HHH", (board << 4) | dac, start_addr,
                           start_addr + len(data)//2 - 1) + data
        data = data.replace(self._escape, self._escape + self._escape)
        self.write(data)

    def write_channel(self, channel):
        self.write_mem(self.channels.index(channel),
                       channel.serialize())

    def write_all(self):
        for channel in self.channels:
            self.write_mem(self.channels.index(channel),
                           channel.serialize())

    def write_table(self, channel):
        # no segment placement
        # no segment writing
        self.write_mem(channel, self.channels[channel].table())

    def write_segment(self, channel, segment):
        # no collision check
        s = self.channels[channel].segments[segment]
        self.write_mem(channel, s.data, s.adr)

    def program(self, program):
        self.clear_all()
        for frame_data in program:
            segments = [c.new_segment() for c in self.channels]
            for i, line in enumerate(frame_data):  # segments are concatenated
                dac_divider = line.get("dac_divider", 1)
                shift = int(log2(dac_divider))
                assert 2**shift == dac_divider
                duration = line["duration"]
                trigger = line.get("trigger", False)
                if i == 0:
                    assert trigger
                    trigger = False  # use wait on the last line
                eof = i == len(frame_data) - 1
                for segment, data in zip(segments, line.get("channel_data")):
                    assert len(data) == 1
                    for target, target_data in data.items():
                        getattr(segment, target)(
                            shift=shift, duration=duration,
                            trigger=trigger, wait=eof, jump=eof,
                            **target_data)
        self.write_all()
