#!/usr/bin/env python3

# This script makes the following assumptions:
#  * tcpdump has CAP_NET_RAW capabilities set
#    use # setcap cap_net_raw+eip /usr/sbin/tcpdump

import argparse
import os
import subprocess

from artiq.tools import verbosity_args, init_logger, logger, SSHClient


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device "
                                                 "packet capture tool")

    verbosity_args(parser)

    parser.add_argument("-H", "--host", metavar="HOST",
                        type=str, default="lab.m-labs.hk",
                        help="SSH host where the development board is located")
    parser.add_argument("-D", "--device", metavar="DEVICE",
                        type=str, default="kc705.lab.m-labs.hk",
                        help="address or domain corresponding to the development board")
    parser.add_argument("-f", "--file", metavar="PCAP_FILE",
                        type=str, default="coredevice.pcap",
                        help="Location to retrieve the pcap file into")

    parser.add_argument("command", metavar="COMMAND",
                        type=str, default=[], nargs=argparse.REMAINDER,
                        help="command to execute while capturing")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    client = SSHClient(args.host)

    sftp = client.get_sftp()
    tcpdump = client.spawn_command(
        "/usr/sbin/tcpdump host {device} -w {tmp}/trace.pcap", get_pty=True,
        device=args.device)

    try:
        subprocess.check_call(args.command)
    except subprocess.CalledProcessError:
        logger.error("Command failed")
        sys.exit(1)

    tcpdump.close()
    sftp.get("{tmp}/trace.pcap".format(tmp=client.tmp),
             args.file + ".new")
    os.rename(args.file + ".new", args.file)
    logger.info("Pcap file {file} retrieved".format(file=args.file))
