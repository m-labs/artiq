#!/usr/bin/env python3

# Based on code by Robert Jordens <jordens@gmail.com>, 2012

import argparse
import time

from scipy import interpolate
import numpy as np

from artiq.management.pc_rpc import Client


def _get_args():
    parser = argparse.ArgumentParser(description="""PDQ2 client.
        Evaluates times and voltages, interpolates and uploads
        them to the controller.""")
    parser.add_argument("-s", "--server", default="::1",
                        help="hostname or IP of the controller to connect to")
    parser.add_argument("--port", default=3252, type=int,
                        help="TCP port to use to connect to the controller")
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
                        help="interpolation"
                             " (0: const, 1: lin, 2: quad, 3: cubic)"
                             " [%(default)s]")
    parser.add_argument("-m", "--dcm", default=None, type=int,
                        help="choose fast 100MHz clock [%(default)s]")
    parser.add_argument("-x", "--demo", default=False, action="store_true",
                        help="demo mode: pulse and chirp,"
                             " 1V*ch+0.1V*frame [%(default)s]")
    parser.add_argument("-p", "--plot", help="plot to file [%(default)s]")
    parser.add_argument("-r", "--reset", default=False,
                        action="store_true", help="do reset before")
    parser.add_argument("-b", "--bit", default=False,
                        action="store_true", help="do bit test")
    return parser.parse_args()


def _main():
    args = _get_args()
    dev = Client(args.server, args.port, "pdq2")
    dev.init()

    if args.reset:
        dev.flush_escape()
        dev.write_cmd("RESET_EN")
        time.sleep(.1)
    if args.dcm:
        dev.write_cmd("DCM_EN")
        dev.set_freq(100e6)
    elif args.dcm == 0:
        dev.write_cmd("DCM_DIS")
        dev.set_freq(50e6)
    dev.write_cmd("START_DIS")

    num_channels = dev.get_num_channels()
    num_frames = dev.get_num_frames()
    times = eval(args.times, globals(), {})
    voltages = eval(args.voltages, globals(), dict(t=times))

    if args.demo:
        # FIXME
        channels = [args.channel] if args.channel < num_channels \
            else range(num_channels)
        frames = [args.frame] if args.frame < num_frames \
            else range(num_frames)
        for channel in channels:
            f = []
            for frame in frames:
                vi = .1*frame + channel + voltages
                pi = 2*np.pi*(.01*frame + .1*channel + 0*voltages)
                fi = 10e6*times/times[-1]
                f.append(b"".join([
                    dev.frame(times, vi, order=args.order, end=False),
                    dev.frame(2*times, voltages, pi, fi, trigger=False),
                    # dev.frame(2*times, 0*vi+.1, 0*pi, 0*fi+1e6),
                    # dev.frame(times, 0*vi, order=args.order, silence=True),
                ]))
            board, dac = divmod(channel, dev.num_dacs)
            dev.write_data(dev.add_mem_header(board, dac, dev.map_frames(f)))
    elif args.bit:
        map = [0] * num_frames
        t = np.arange(2*16) * 1.
        v = [-1, 0, -1]
        for i in range(15):
            vi = 1 << i
            v.extend([vi - 1, vi])
        v = np.array(v)*dev.get_max_out()/(1 << 15)
        t, v = t[:3], v[:3]
        # print(t, v)
        for channel in range(num_channels):
            dev.multi_frame([(t, v)], channel=channel, order=0, map=map,
                            shift=15, stop=False, trigger=False)
    else:
        tv = [(times, voltages)]
        map = [None] * num_frames
        map[args.frame] = 0
        dev.multi_frame(tv, channel=args.channel, order=args.order, map=map)

    dev.write_cmd("START_EN")
    if not args.disarm:
        dev.write_cmd("ARM_EN")
    if args.free:
        dev.write_cmd("TRIGGER_EN")

    if args.plot:
        from matplotlib import pyplot as plt
        fig, ax0 = plt.subplots()
        ax0.plot(times, voltages, "xk", label="points")
        if args.order:
            spline = interpolate.splrep(times, voltages, k=args.order)
            ttimes = np.arange(0, times[-1], 1/dev.get_freq())
            vvoltages = interpolate.splev(ttimes, spline)
            ax0.plot(ttimes, vvoltages, ",b", label="interpolation")
        fig.savefig(args.plot)

if __name__ == "__main__":
    _main()
