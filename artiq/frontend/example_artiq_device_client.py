#!/usr/bin/env python3

import argparse

from artiq.protocols.pc_rpc import Client


def define_parser():
    parser = argparse.ArgumentParser(
        description="example_artiq_device_client",
        epilog="This is a m-labs.com ARTIQ "
        "client that serves as a template for interaction with ARTIQ devices. == "
        "The hardware interface is a serial port.")

    # following are default arguments that should be common to any ARTIQ device client.
    parser.add_argument("--bind", default="::1",
        help="hostname or IP address to bind to (::1 is localhost)")
    parser.add_argument("--port", default=3254, type=int,
        help="TCP port to listen to 3254")
    parser.add_argument("--verbose", action="store_true",
        help="increase output verbosity")

    # following are for interacting with a specific device
    # roughly, each member function of Example_ARTIQ_Device has its own entry below
    subparsers = parser.add_subparsers(dest="subparser_name")

    restricted_float_freq = partial(restricted_float, 0.0, 171.1276031)
    parser_setfreq = subparsers.add_parser("freq",
                                           help="set frequency")
    parser_setfreq.add_argument("f", type=restricted_float_freq,
                                help="frequency in MHz"
                                "[0.0,171.1276031]")
    parser_setfreq.add_argument("--channel", default=-1, type=int,
                        choices=range(0, 4),
                        help="which channel to set; default is ALL")

    parser_setphase = subparsers.add_parser("phase",
                                            help="set phase")
    parser_setphase.add_argument(
        "p",type=partial(restricted_float, 0.0, 1.0),
        nargs=4,
        help="p0 p1 p2 p3 are phases for all four "
        "channels in cycles (1=360 deg)")

    parser_gain=subparsers.add_parser("gain", help="set output gain")
    parser_gain.add_argument("g",
                type=partial(restricted_float, 0.0, 1.0),
                help="waveform amplitude [0.0, 1.0]")
    parser_gain.add_argument("--channel",
                        default=-1, type = int,
                        choices=range(0, 4),
                        help="which channel to set; default is ALL")

    parser_sweep_freq = subparsers.add_parser("sweep-freq",
                                              help="sweep frequency")
    parser_sweep_freq.add_argument("p0", type=restricted_float_freq,
                                    help="starting freq in MHz")
    parser_sweep_freq.add_argument("p1", type=restricted_float_freq,
                                    help="ending freq in MHz")
    parser_sweep_freq.add_argument("t", type=float,
                                    help="sweep time in sec")
    parser_sweep_freq.add_argument("--channel",
                        default=-1, type=int,
                        choices=range(0, 4),
                        help="which channel to set; default is ALL")

    parser_reset = subparsers.add_parser("reset", help="reset device")
    parser_reset.add_argument("reset",
                help="reset device", action="store_true")
    parser_eeprom = subparsers.add_parser("save-to-eeprom",
                                          help="save to EEPROM")
    parser_eeprom.add_argument("save-to-eeprom",
                        action="store_true",
                        help="saves current state into EEPROM "
                        "and sets valid flag; state used as default"
                        " upon next power up or reset")
    return parser


def restricted_float(val_min, val_max, x):
    """do range checking on a variable
    """
    x = float(x)
    if x < val_min or x > val_max:
        raise argparse.ArgumentTypeError(
            "{:f} not in range [{:f}, {:f}]".format(x, val_min, val_max))
    return x

def _get_args():
    p = define_parser()
    return p.parse_args()


def main():
    args = _get_args()
    remote = Client(args.bind, args.port, "novatech409B")
    try:
        if args.verbose:
            print(args)
        if args.echo:
            r = remote.echo(args.echo[0])
            print(r)
        elif args.subparser_name:
            if args.subparser_name == "phase":
                remote.set_phase_all(args.p)
            elif args.subparser_name == "freq":
                if args.channel == -1:
                    remote.set_freq_all_phase_continuous(args.f)
                else:
                    remote.set_freq(args.channel, args.f)
            elif args.subparser_name == "sweep-freq":
                remote.freq_sweep_all_phase_continuous(
                    args.f0, args.f1, args.t)
            elif args.subparser_name == "gain":
                if args.channel == -1:
                    remote.output_scale_all(args.g)
                else:
                    remote.output_scale(args.channel, args.g)
            elif args.subparser_name == "reset":
                remote.reset()
            elif args.args.subparser_eeprom == "save-to-eeprom":
                remote.save_state_to_eeprom()
    finally:
        remote.close_rpc()

if __name__ == "__main__":
    main()