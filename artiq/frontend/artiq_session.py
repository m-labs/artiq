#!/usr/bin/env python3

import argparse
import sys
import subprocess
from artiq import __version__ as artiq_version


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ session manager. "
                    "Automatically runs the master, dashboard and "
                    "local controller manager on the current machine. "
                    "The latter requires the artiq-comtools package to "
                    "be installed.")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")
    parser.add_argument("-m", action="append", default=[],
                        help="add argument to the master command line")
    parser.add_argument("-d", action="append", default=[],
                        help="add argument to the dashboard command line")
    parser.add_argument("-c", action="append", default=[],
                        help="add argument to the controller manager command line")
    return parser


def main():
    args = get_argparser().parse_args()

    master_cmd    = [sys.executable, "-u", "-m", "artiq.frontend.artiq_master"]
    dashboard_cmd = [sys.executable,       "-m", "artiq.frontend.artiq_dashboard"]
    ctlmgr_cmd    = [sys.executable,       "-m", "artiq_comtools.artiq_ctlmgr"]
    master_cmd    += args.m
    dashboard_cmd += args.d
    ctlmgr_cmd    += args.c

    with subprocess.Popen(master_cmd,
                          stdout=subprocess.PIPE, universal_newlines=True,
                          bufsize=1) as master:
        master_ready = False
        for line in iter(master.stdout.readline, ""):
            sys.stdout.write(line)
            if line.rstrip() == "ARTIQ master is now ready.":
                master_ready = True
                break
        if master_ready:
            with subprocess.Popen(dashboard_cmd):
                with subprocess.Popen(ctlmgr_cmd):
                    for line in iter(master.stdout.readline, ""):
                        sys.stdout.write(line)
        else:
            print("session: master failed to start, exiting.")


if __name__ == "__main__":
    main()
