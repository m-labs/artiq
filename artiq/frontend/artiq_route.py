#!/usr/bin/env python3

import argparse


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ DRTIO routing table "
                                                 "manipulation tool")

    parser.add_argument("file", metavar="FILE", type=str,
                        help="target file")

    action = parser.add_subparsers(dest="action")
    action.required = True

    action.add_parser("init", help="create a new empty routing table")
    
    action.add_parser("show", help="show contents of routing table")

    a_set = action.add_parser("set", help="set routing table entry")
    a_set.add_argument("destination", metavar="DESTINATION", type=int,
                       help="destination to operate on")
    a_set.add_argument("hop", metavar="HOP", type=int, nargs="*",
                       help="hop(s) to the destination")

    return parser


DEST_COUNT = 256
MAX_HOPS = 32


def init(filename):
    with open(filename, "wb") as f:
        f.write(b"\xff"*(DEST_COUNT*MAX_HOPS))


def show_routes(filename):
    routes = []
    with open(filename, "rb") as f:
        for i in range(DEST_COUNT):
            hops = [int.from_bytes(f.read(1), "big") for j in range(MAX_HOPS)]
            routes.append(hops)

    for destination, route in enumerate(routes):
        if route[0] != 0xff:
            fmt = "{:3d}:".format(destination)
            for hop in route:
                if hop == 0xff:
                    break
                fmt += " {:3d}".format(hop)
            print(fmt)


def set_route(filename, destination, hops):
    with open(filename, "r+b") as f:
        if destination >= DEST_COUNT:
            raise ValueError("destination must be less than {}".format(DEST_COUNT))
        f.seek(destination*MAX_HOPS)

        if len(hops) + 1 >= MAX_HOPS:
            raise ValueError("too many hops")
        for hop in hops:
            if hop >= 0xff:
                raise ValueError("all hops must be less than 255")

        hops = hops + [0xff]*(MAX_HOPS-len(hops))
        f.write(bytes(hops))


def main():
    args = get_argparser().parse_args()
    if args.action == "init":
        init(args.file)
    elif args.action == "show":
        show_routes(args.file)
    elif args.action == "set":
        set_route(args.file, args.destination, args.hop)
    else:
        raise ValueError

if __name__ == "__main__":
    main()
