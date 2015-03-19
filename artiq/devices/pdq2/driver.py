# Robert Jordens <jordens@gmail.com>, 2012-2015

import logging
import struct
import warnings

import numpy as np
from scipy import interpolate
import serial

logger = logging.getLogger(__name__)


class Segment:
    def __init__(self):
        self.data = b""

    def line(self, typ, dt, data, trigger=False, silence=False,
             aux=False, shift=0, end=False, clear=False, wait=False):
        assert len(data) % 2 == 0, data
        assert len(data)//2 <= 14
        #assert dt*(1 << shift) > 1 + len(data)//2
        head = (
            1 + len(data)//2 | (typ << 4) | (trigger << 6) | (silence << 7) |
            (aux << 8) | (shift << 9) | (end << 13) | (clear << 14) |
            (wait << 15)
        )
        self.data += struct.pack("<HH", head, dt) + data

    @staticmethod
    def pack(widths, values):
        fmt = "<"
        ud = []
        for width, value in zip(widths, values):
            if width == 3:
                ud.append(value & 0xffff)
                fmt += "H"
                value >>= 16
                width -= 1
            ud.append(value)
            fmt += " hi"[width]
        try:
            return struct.pack(fmt, *ud)
        except struct.error as e:
            logger.error("%s as %s: %s", ud, fmt, e)
            raise e

    def lines(self, typ, dt, widths, v, first={}, mid={}, last={}, shift=0):
        n = len(dt) - 1
        dt = dt.astype(np.uint16)
        v = v.astype(np.int64)
        for i, (dti, vi) in enumerate(zip(dt, v)):
            opts = mid
            if i == 0:
                opts = first
            elif i == n:
                opts = last
            data = self.pack(widths, vi)
            self.line(typ, dti, data, shift=shift, **opts)

    @staticmethod
    def interpolate(t, v, order, t_eval, widths=None):
        """Spline interpolating derivatives for t,v.
        The returned spline coefficients are one shorter than t
        """
        if order == 0:
            return np.rint(v[:, None])
        # FIXME: does not ensure that interpolates do not clip
        s = interpolate.splrep(t, v, k=order)
        # FIXME: needs k knots outside t_eval
        # dv = np.array(interpolate.spalde(t_eval, s))
        dv = np.array([interpolate.splev(t_eval, s, der=i, ext=0)
                       for i in range(order + 1)]).T
        # correct for adder chain latency
        if order > 1:
            dv[:, 1] += dv[:, 2]/2
        if order > 2:
            dv[:, 1] += dv[:, 3]/6
            dv[:, 2] += dv[:, 3]
        if widths is not None:
            dv *= 1 << 16*widths
        return np.rint(dv)

    def line_times(self, t, tr=None):
        if tr is None:
            tr = np.rint(t)
        if len(tr) == 1:
            return None, np.array([1])
        dt = np.diff(tr)
        assert np.all(dt >= 0)
        assert np.all(dt < (1 << 16))
        return tr[:-1], dt

    def dac(self, t, v, first={}, mid={}, last={},
            shift=0, tr=None, order=3, stop=True):
        widths = np.array([1, 2, 3, 3])
        tr, dt = self.line_times(t, tr)
        dv = self.interpolate(t, v, order, tr, widths[:order + 1] - 1)
        self.lines(0, dt, widths, dv, first, mid, mid if stop else last, shift)
        if stop:
            self.line(0, 2, self.pack([1], [int(round(v[-1]))]), **last)

    def dds(self, t, v, p=None, f=None, first={}, mid={}, last={},
            shift=0, tr=None, order=3, stop=True):
        widths = np.array([1, 2, 3, 3, 1, 2, 2])
        tr, dt = self.line_times(t, tr)
        dv = self.interpolate(t, v, order, tr, widths[:order + 1] - 1)
        if p is not None:
            assert order == 3
            dp = self.interpolate(t, p, 1, tr)[:, :1]
            dv = np.concatenate((dv, dp), axis=1)
            if f is not None:
                df = self.interpolate(t, f, 1, tr, widths[-2:] - 1)
                dv = np.concatenate((dv, df), axis=1)
        self.lines(1, dt, widths, dv, first, mid, mid if stop else last, shift)
        if stop:
            dv = [int(round(v[-1])), 0, 0, 0]
            if p is not None:
                dv.append(int(round(p[-1])))
                if f is not None:
                    dv.append(int(round(f[-1])))
            self.line(1, 2, self.pack(widths, dv), **last)


class Channel:
    max_data = 4*(1 << 10)  # 8kx16 8kx16 4kx16
    num_frames = 8
    max_val = 1 << 15  # int16 bit DAC
    max_time = 1 << 16  # uint16 bit timer
    cordic_gain = 1.
    for i in range(16):
        cordic_gain *= np.sqrt(1 + 2**(-2*i))
    max_out = 10.
    freq = 50e6  # samples/s

    def __init__(self):
        self.segments = []

    def clear(self):
        del self.segments[:]

    def new_segment(self):
        # assert len(self.segments) < self.num_frames
        segment = Segment()
        self.segments.append(segment)
        return segment

    def segment(self, t, v, p=None, f=None,
                order=3, aux=False, shift=0, trigger=True, end=True,
                silence=False, stop=True, clear=True, wait=False):
        segment = self.new_segment()
        t = t*(self.freq/2**shift)
        v = np.clip(v/self.max_out, -1, 1)
        order = min(order, len(t) - 1)
        first = dict(trigger=trigger, clear=clear, aux=aux)
        mid = dict(aux=aux)
        last = dict(silence=silence, end=end, wait=wait, aux=aux)
        if p is None:
            v = v*self.max_val
            segment.dac(t, v, first, mid, last, shift=shift, order=order,
                        stop=stop)
        else:
            v = v*(self.max_val/self.cordic_gain)
            p = p*(self.max_val/np.pi)
            if f is not None:
                f = f*(self.max_val/self.freq)
            segment.dds(t, v, p, f, first, mid, last, shift=shift,
                        order=order, stop=stop)
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
    num_boards = 3
    num_channels = num_dacs*num_boards

    _escape = b"\xa5"
    _commands = "RESET TRIGGER ARM DCM START".split()

    def __init__(self, url=None, dev=None):
        if dev is None:
            dev = serial.serial_for_url(url)
        self.dev = dev
        self.channels = [Channel() for i in range(self.num_channels)]
        self.set_freq()

    def set_freq(self, f=50e6):
        for c in self.channels:
            c.freq = f

    def close(self):
        self.dev.close()
        del self.dev

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

    def write_channel(self, channel, entry=None):
        self.write_mem(self.channels.index(channel),
                       channel.serialize(entry))

    def write_all(self):
        for channel in self.channels:
            self.write_mem(self.channels.index(channel),
                           channel.serialize())

    def write_table(self, channel, segments=None):
        # no segment placement
        # no segment writing
        self.write_mem(channel, self.channels[channel].table(segments))

    def write_segment(self, channel, segment):
        # no collision check
        s = self.channels[channel].segments[segment]
        self.write_mem(channel, s.data, s.adr)

    def multi_segment(self, times_voltages, channel, map=None, **kwargs):
        warnings.warn("deprecated", DeprecationWarning)
        c = self.channels[channel]
        del c.segments[:]
        for t, v in times_voltages:
            c.segment(t, v, **kwargs)
        return c.serialize(map)
