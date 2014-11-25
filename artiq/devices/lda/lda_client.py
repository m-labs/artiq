#!/usr/bin/env python3
from artiq.management.pc_rpc import Client
import argparse


def get(remote):
    return remote.get_attenuation()


def set(remote, attenuation):
    remote.set_attenuation(attenuation)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server', default="::1",
                        help="The IP address or hostname of the controller")
    parser.add_argument('-p', '--port', default=7777, type=int,
                        help="The TCP port the controller listens to")
    parser.add_argument('-a', '--attenuation', type=float,
                        help="The attenuation value you want to set")
    args = parser.parse_args()

    remote = Client(args.server, args.port, "lda")

    try:
        if args.attenuation is None:
            print("Current attenuation: {}".format(get(remote)))
        else:
            set(remote, args.attenuation)
    except Exception as e:
        print("exception: {}".format(e))
        remote.close_rpc()
