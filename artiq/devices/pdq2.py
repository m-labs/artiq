#!/usr/bin/python
# -*- coding: utf8 -*-
#
# Robert Jordens <jordens@gmail.com>, 2012

import logging, struct
import numpy as np
from scipy import interpolate
import warnings

logger = logging.getLogger("Pdq2")


Ftdi = None


try:
    import pylibftdi

    class PyFtdi:
        def __init__(self, serial=None):
            self.dev = pylibftdi.Device(device_id=serial)

        def write(self, data):
            written = self.dev.write(data)
            if written < 0:
                raise pylibftdi.FtdiError(written,
                        self.dev.get_error_string())
            return written

        def close(self):
            self.dev.close()
            del self.dev

    Ftdi = PyFtdi
except ImportError:
    pass


try:
    import ftd2xx

    class D2xxFtdi:
        def __init__(self, serial=None):
            if serial is not None:
                self.dev = ftd2xx.openEx(serial)
            else:
                self.dev = ftd2xx.open()
            self.dev.setTimeouts(read=5000, write=5000)

        def write(self, data):
            written = self.dev.write(str(data))
            return written

        def close(self):
            self.dev.close()
            del self.dev

    Ftdi = D2xxFtdi
except ImportError:
    pass


if Ftdi is None:

    class FileFtdi:
        def __init__(self, serial="unknown"):
            self.fil = open("pdq_%s_ftdi.bin" % serial, "wb")

        def write(self, data):
            self.fil.write(data)
            return len(data)

        def close(self):
            self.fil.close()
            del self.fil

    warnings.warn("no ftdi library found. writing to files")
    Ftdi = FileFtdi


class Pdq2:
    """
    PDQ DAC (a.k.a. QC_Waveform)
    """
    max_val = 1<<15 # signed 16 bit DAC
    max_out = 10.
    freq = 50e6 # samples/s
    max_time = 1<<16 # unsigned 16 bit timer
    num_dacs = 3
    num_frames = 8
    num_channels = 9
    max_data = 4*(1<<10) # 8kx16 8kx16 4kx16
    escape_char = b"\xa5"
    cordic_gain = 1.
    for i in range(16):
        cordic_gain *= np.sqrt(1 + 2**(-2*i))

    commands = {
            "RESET_EN":    b"\x00",
            "RESET_DIS":   b"\x01",
            "TRIGGER_EN":  b"\x02",
            "TRIGGER_DIS": b"\x03",
            "ARM_EN":      b"\x04",
            "ARM_DIS":     b"\x05",
            "DCM_EN":      b"\x06",
            "DCM_DIS":     b"\x07",
            "START_EN":    b"\x08",
            "START_DIS":   b"\x09",
            }

    def __init__(self, serial=None):
        self.serial = serial
        self.dev = Ftdi(serial)

    def close(self):
        self.dev.close()
        del self.dev

    def cmd(self, cmd):
        return self.escape_char + self.commands[cmd]

    def write_cmd(self, cmd):
        return self.write(self.cmd(cmd))

    def escape(self, data):
        return data.replace(self.escape_char, self.escape_char +
                self.escape_char)

    def write(self, *segments):
        """
        writes data segments to device
        """
        for segment in segments:
            written = self.dev.write(segment)
            if written != len(segment):
                raise IOError("wrote %i of %i" % (written, len(segment)))

    def write_data(self, *segments):
        return self.write(*(self.escape(seg) for seg in segments))

    def line_times(self, t, shift=0):
        scale = self.freq/2**shift
        t = t*scale
        tr = np.rint(t)
        dt = np.diff(tr)
        return t, tr, dt

    def interpolate(self, t, v, order, shift=0, tr=None):
        """
        calculate spline interpolation derivatives for data
        according to interpolation order
        also differentiates times (implicitly shifts to 0) and removes
        the last value (irrelevant since the frame ends here)
        """
        if order == 0:
            return [v[:-1]]
        spline = interpolate.splrep(t, v, k=order)
        if tr is None:
            tr = t
        dv = [interpolate.splev(tr[:-1], spline, der=i)
                for i in range(order + 1)]
        # correct for adder chain latency
        correction_map = [
                (1, -1/2., 2),
                (1, -1/6., 3),
                (2,   -1., 3),
                ]
        for i, c, j in correction_map:
            if j >= len(dv):
                break
            dv[i] -= c*dv[j]
        return dv

    def pack_frame(self, *parts_dtypes):
        frame = []
        for part, dtype in parts_dtypes:
            if dtype == "i6":
                part = part.astype("<i8")
                frame.append(part.astype("<i4"))
                frame.append((part >> 32).astype("<i2"))
            else:
                frame.append(part.astype("<" + dtype))
        frame = np.rec.fromarrays(frame) # interleave
        logger.debug("frame %s dtype %s shape %s length %s",
                frame, frame.dtype, frame.shape, len(bytes(frame.data)))
        return bytes(frame.data)

    def frame(self, t, v, p=None, f=None,
            order=3, aux=None, shift=0, trigger=True, end=True,
            silence=False, stop=True, clear=True, wait=False):
        """
        serialize frame data
        voltages in volts, times in seconds
        """
        words = [1, 2, 3, 3, 1, 2, 2]
        n = order + 1
        if f is not None:
            n += 2
            if p is None:
                p = np.zeros_like(f)
        if p is not None:
            n += 1
        length = 1 + sum(words[:n])
        parts = []

        head = np.zeros(len(t) - 1, "<u2")
        head[:] |= length # 4
        if p is not None:
            head[:] |= 1<<4 # typ # 2
        head[0] |= trigger<<6 # 1
        head[-1] |= (not stop and silence)<<7 # 1
        if aux is not None:
            head[:] |= aux[:len(head)]<<8 # 1
        head[:] |= shift<<9 # 4
        head[-1] |= (not stop and end)<<13 # 1
        head[0] |= clear<<14 # 1
        head[-1] |= (not stop and wait)<<15 # 1
        parts.append((head, "u2"))

        t, tr, dt = self.line_times(t, shift)
        assert np.all(dt*2**shift > 1 + length), (dt, length)
        assert np.all(dt < self.max_time), dt

        parts.append((dt, "u2"))

        v = np.clip(v/self.max_out, -1, 1)
        if p is not None:
            v /= self.cordic_gain
        for dv, w in zip(self.interpolate(t, v, order, shift, tr), words):
            parts.append((np.rint(dv*(2**(16*w - 1))), "i%i" % (2*w)))

        if p is not None:
            p = p/(2*np.pi)
            for dv, w in zip(self.interpolate(t, p, 0, shift, tr), [1]):
                parts.append((np.rint(dv*(2**(16*w))), "u%i" % (2*w)))

        if f is not None:
            f = f/self.freq
            for dv, w in zip(self.interpolate(t, f, 1, shift, tr), [2, 2]):
                parts.append((np.rint(dv*(2**(16*w))), "i%i" % (2*w)))

        frame = self.pack_frame(*parts)

        if stop:
            if p is not None:
                frame += struct.pack("<HH hiihih H ii", (15<<0) | (1<<4) |
                        (silence<<7) | (end<<13) | (wait<<15),
                        1, int(v[-1]*2**15), 0, 0, 0, 0, 0,
                        int(p[-1]*2**16), int(f[-1]*2**31), 0)
            else:
                frame += struct.pack("<HH h", (2<<0) |
                        (silence<<7) | (end<<13) | (wait << 15),
                        1, int(v[-1]*2**15))
        return frame

    def line(self, dt, v=(), a=(), p=(), f=(), typ=0,
            silence=False, end=False, trigger=False, aux=False,
            clear=False):
        raise NotImplementedError
        fmt = "<HH"
        parts = [0, int(round(dt*self.freq))]
        for vi, wi in zip(v, [1, 2, 3, 3]):
            vi = int(round(vi*(2**(16*wi - 1))))
            if wi == 3:
                fmt += "Ih"
                parts += [vi & 0xffffffff, vi >> 32]
            else:
                fmt += "bih"[wi]
                parts += [vi]
        if p is not None:
            typ = 1

    def map_frames(self, frames, map=None):
        table = []
        adr = self.num_frames
        for frame in frames:
            table.append(adr)
            adr += len(frame)//2
        assert adr <= self.max_data, adr
        t = []
        for i in range(self.num_frames):
            if map is not None and len(map) > i:
                i = map[i]
            if i is not None and len(table) > i:
                i = table[i]
            else:
                i = 0
            t.append(i)
        t = struct.pack("<" + "H"*self.num_frames, *t)
        return t + b"".join(frames)

    def add_mem_header(self, board, dac, data, adr=0):
        assert dac in range(self.num_dacs)
        head = struct.pack("<HHH", (board << 4) | dac,
                adr, adr + len(data)//2 - 1)
        return head + data

    def multi_frame(self, times_voltages, channel, map=None, **kwargs):
        frames = [self.frame(t, v, **kwargs) for t, v in times_voltages]
        data = self.map_frames(frames, map)
        board, dac = divmod(channel, self.num_dacs)
        data = self.add_mem_header(board, dac, data)
        return data


def _main():
    import argparse
    import time

    parser = argparse.ArgumentParser(description="""PDQ2 frontend.
            Evaluates times and voltages, interpolates and uploads
            them.""")
    parser.add_argument("-s", "--serial", default=None,
            help="device (FT245R) serial string [first]")
    parser.add_argument("-c", "--channel", default=0, type=int,
            help="channel: 3*board_num+dac_num [%(default)s]")
    parser.add_argument("-f", "--frame", default=0, type=int,
            help="frame [%(default)s]")
    parser.add_argument("-e", "--free", default=False,
            action="store_true",
            help="software trigger [%(default)s]")
    parser.add_argument("-n", "--disarm", default=False,
            action="store_true",
            help="disarm group [%(default)s]")
    parser.add_argument("-t", "--times",
            default="np.arange(5)*1e-6",
            help="sample times (s) [%(default)s]")
    parser.add_argument("-v", "--voltages",
            default="(1-np.cos(t/t[-1]*2*np.pi))/2",
            help="sample voltages (V) [%(default)s]")
    parser.add_argument("-o", "--order", default=3, type=int,
            help="interpolation (0: const, 1: lin, 2: quad, 3: cubic)"
                 " [%(default)s]")
    parser.add_argument("-m", "--dcm", default=None, type=int,
            help="choose fast 100MHz clock [%(default)s]")
    parser.add_argument("-x", "--demo", default=False, action="store_true",
            help="demo mode: pulse and chirp, 1V*ch+0.1V*frame [%(default)s]")
    parser.add_argument("-p", "--plot", help="plot to file [%(default)s]")
    parser.add_argument("-d", "--debug", default=False,
            action="store_true", help="debug communications")
    parser.add_argument("-r", "--reset", default=False,
            action="store_true", help="do reset before")
    parser.add_argument("-b", "--bit", default=False,
            action="store_true", help="do bit test")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    times = eval(args.times, globals(), {})
    voltages = eval(args.voltages, globals(), dict(t=times))

    dev = Pdq2(serial=args.serial)

    if args.reset:
        dev.write(b"\x00") # flush any escape
        dev.write_cmd("RESET_EN")
        time.sleep(.1)
    if args.dcm:
        dev.write_cmd("DCM_EN")
        dev.freq = 100e6
    elif args.dcm == 0:
        dev.write_cmd("DCM_DIS")
        dev.freq = 50e6
    dev.write_cmd("START_DIS")

    if args.demo:
        channels = [args.channel] if args.channel < dev.num_channels \
            else range(dev.num_channels)
        frames = [args.frame] if args.frame < dev.num_frames \
            else range(dev.num_frames)
        for channel in channels:
            f = []
            for frame in frames:
                vi = .1*frame + channel + voltages
                pi = 2*np.pi*(.01*frame + .1*channel + 0*voltages)
                fi = 10e6*times/times[-1]
                f.append(b"".join([
                    dev.frame(times, vi, order=args.order, end=False),
                    dev.frame(2*times, voltages, pi, fi, trigger=False),
                    #dev.frame(2*times, 0*vi+.1, 0*pi, 0*fi+1e6),
                    #dev.frame(times, 0*vi, order=args.order, silence=True),
                ]))
            board, dac = divmod(channel, dev.num_dacs)
            dev.write_data(dev.add_mem_header(board, dac, dev.map_frames(f)))
    elif args.bit:
        map = [0] * dev.num_frames
        t = np.arange(2*16) * 1.
        v = [-1, 0, -1]
        for i in range(15):
            vi = 1<<i
            v.extend([vi - 1, vi])
        v = np.array(v)*dev.max_out/(1<<15)
        t, v = t[:3], v[:3]
        #print(t, v)
        for channel in range(dev.num_channels):
            dev.write_data(dev.multi_frame([(t, v)], channel=channel,
                order=0, map=map, shift=15, stop=False, trigger=False))
    else:
        tv = [(times, voltages)]
        map = [None] * dev.num_frames
        map[args.frame] = 0
        dev.write_data(dev.multi_frame(tv, channel=args.channel,
                                       order=args.order, map=map))

    dev.write_cmd("START_EN")
    if not args.disarm:
        dev.write_cmd("ARM_EN")
    if args.free:
        dev.write_cmd("TRIGGER_EN")
    dev.close()

    if args.plot:
        from matplotlib import pyplot as plt
        fig, ax0 = plt.subplots()
        ax0.plot(times, voltages, "xk", label="points")
        if args.order:
            spline = interpolate.splrep(times, voltages, k=args.order)
            ttimes = np.arange(0, times[-1], 1/dev.freq)
            vvoltages = interpolate.splev(ttimes, spline)
            ax0.plot(ttimes, vvoltages, ",b", label="interpolation")
        fig.savefig(args.plot)


if __name__ == "__main__":
    _main()
