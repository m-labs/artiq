#!/usr/bin/python
# Copyright (C) 2012-2015 Robert Jordens <jordens@gmail.com>

import argparse

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
    parser.add_argument("-o", "--order", default=3, type=int,
                        help="interpolation (0: const, 1: lin, 2: quad,"
                        " 3: cubic) [%(default)s]")
    parser.add_argument("-e", "--free", default=False, action="store_true",
                        help="software trigger [%(default)s]")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)
    dev = Client(args.server, args.port, "pdq2")

    freq = dev.get_freq()
    times = np.around(eval(args.times, globals(), {})*freq)
    voltages = eval(args.voltages, globals(), dict(t=times/freq))

    dt = np.diff(times.astype(np.int))
    if args.order:
        tck = interpolate.splrep(times, voltages, k=args.order, s=0)
        u = interpolate.spalde(times, tck)
    else:
        u = voltages[:, None]
    segment = []
    for dti, ui in zip(dt, u):
        segment.append({
            "duration": int(dti),
            "channel_data": [{
                "bias": {
                    "amplitude": [float(uij) for uij in ui]
                }
            }]
        })
    program = [[] for i in range(args.frame)]
    program.append(segment)
    dev.park()
    dev.program(program, [args.channel])
    dev.unpark()
    dev.cmd("TRIGGER", args.free)


if __name__ == "__main__":
    main()
