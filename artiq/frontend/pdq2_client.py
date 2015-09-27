#!/usr/bin/python
# Copyright (C) 2012-2015 Robert Jordens <jordens@gmail.com>

import argparse
import time

from scipy import interpolate
import numpy as np

from artiq.protocols.pc_rpc import Client
from artiq.tools import verbosity_args, init_logger


def get_argparser():
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
    parser.add_argument("-t", "--times", default="np.arange(5)*1e-6",
                        help="sample times (s) [%(default)s]")
    parser.add_argument("-u", "--voltages",
                        default="(1-np.cos(t/t[-1]*2*np.pi))/2",
                        help="sample voltages (V) [%(default)s]")
    parser.add_argument("-a", "--aux", default=False, action="store_true",
                        help="axiliary digital output [%(default)%s]")
    parser.add_argument("-o", "--order", default=3, type=int,
                        help="interpolation (0: const, 1: lin, 2: quad,"
                        " 3: cubic) [%(default)s]")
    parser.add_argument("-p", "--plot", help="plot to file [%(default)s]")
    parser.add_argument("-r", "--reset", default=False,
                        action="store_true", help="do reset before")
    parser.add_argument("-m", "--dcm", default=False, action="store_true",
                        help="100MHz clock [%(default)s]")
    parser.add_argument("-n", "--disarm", default=False, action="store_true",
                        help="disarm group [%(default)s]")
    parser.add_argument("-e", "--free", default=False, action="store_true",
                        help="software trigger [%(default)s]")
    parser.add_argument("-x", "--demo", default=False, action="store_true",
                        help="demo mode: pulse and chirp, 1V*ch+0.1V*frame"
                        " [%(default)s]")
    parser.add_argument("-b", "--bit", default=False,
                        action="store_true", help="do bit test")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)
    dev = Client(args.server, args.port, "pdq2")
    dev.init()

    if args.reset:
        dev.write(b"\x00\x00")  # flush any escape
        dev.cmd("RESET", True)
        time.sleep(.1)
    dev.cmd("START", False)
    dev.cmd("ARM", False)
    dev.cmd("DCM", args.dcm)
    freq = 100e6 if args.dcm else 50e6
    dev.set_freq(freq)
    num_channels = dev.get_num_channels()
    num_frames = dev.get_num_frames()
    times = eval(args.times, globals(), {})
    voltages = eval(args.voltages, globals(), dict(t=times))

    if args.demo:
        for ch, channel in enumerate(dev.channels):
            entry = []
            for fr in range(dev.channels[0].num_frames):
                vi = .1*fr + ch + voltages
                entry.append(channel.segment(times, vi, order=args.order,
                                             end=False, aux=args.aux))
                pi = 2*np.pi*(-.5 + .01*fr + .1*ch + 0*voltages)
                fi = 10e6*times/times[-1]
                channel.segment(2*times, voltages, pi, fi, trigger=False,
                                silence=True, aux=args.aux)
            dev.write_channel(channel, entry)
    elif args.bit:
        v = [-1, 0, -1]
        # for i in range(15):
        #     v.extend([(1 << i) - 1, 1 << i])
        v = np.array(v)*dev.channels[0].max_out/dev.channels[0].max_val
        t = np.arange(len(v))
        for channel in dev.channels:
            s = channel.segment(t, v, order=0, shift=15, stop=False,
                                trigger=False)
            dev.write_channel(channel, [s for i in range(channel.num_frames)])
    else:
        c = dev.channels[args.channel]
        map = [None] * c.num_frames
        map[args.frame] = c.segment(times, voltages, order=args.order,
                                    aux=args.aux)
        dev.write_channel(c, map)

    dev.cmd("START", True)
    dev.cmd("ARM", not args.disarm)
    dev.cmd("TRIGGER", args.free)

    if args.plot:
        from matplotlib import pyplot as plt
        fig, ax = plt.subplots()
        ax.plot(times, voltages, "xk", label="points")
        if args.order > 0:
            spline = interpolate.splrep(times, voltages, k=args.order)
            ttimes = np.arange(0, times[-1], 1/freq)
            vvoltages = interpolate.splev(ttimes, spline)
            ax.plot(ttimes, vvoltages, ",b", label="interpolation")
        fig.savefig(args.plot)


if __name__ == "__main__":
    main()
