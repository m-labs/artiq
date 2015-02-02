#!/usr/bin/env python3

import argparse
from functools import partial
from artiq.protocols.pc_rpc import Client

# Question: shouldn't this restricted_float() be part of the Quantity class?
# Question: Shouldn't all the parameters passed to drivers be of the Quantity class?
def restricted_float(val_min, val_max, x):
    """do range checking on a variable
    """
    x = float(x)
    if x < val_min or x > val_max:
        raise argparse.ArgumentTypeError(
            "{:f} not in range [{:f}, {:f}]".format(x, val_min, val_max))
    return x

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

    # Following are command line options for interacting with a specific device.
    # Roughly, each member function of the driver Class, here Example_ARTIQ_Device
    # has its own entry below.
    subparsers = parser.add_subparsers(dest="subparser_name")

    # Here, a python feature called a partial is used to check the parameter range
    # of some passed arguments.
    # https://docs.python.org/2/library/argparse.html#partial-parsing
    restricted_myvar = partial(restricted_float, 0.0, 1.0)
    parser_demo_exception_handling = subparsers.add_parser("demo_exception_handling",
                                           help="demonstration of exception handling")
    parser_demo_exception_handling.add_argument("myvar", type=restricted_myvar,
                                help="a number in the range"
                                "[0.0,1.0]")
    parser_demo_exception_handling.add_argument("--optional_argument", default=-1, type=int,
                        choices=range(0, 4),
                        help="an optional argument to pass to demo_exception_handling")

    # All the other member functions in Example_ARTIQ_Device would be parameterized
    # in a similar fashion.

    return parser


def _get_args():
    p = define_parser()
    return p.parse_args()


def main():
    args = _get_args()
    remote = Client(args.bind, args.port, "novatech409b")
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