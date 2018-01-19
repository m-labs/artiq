#!/usr/bin/env python3

# This script makes the following assumptions:
#  * miniconda is installed remotely at ~/miniconda
#  * misoc and artiq are installed remotely via conda

import sys
import argparse
import logging
import subprocess
import socket
import select
import threading
import os
import shutil
import re

from artiq.tools import verbosity_args, init_logger, logger, SSHClient


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ core device development tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    verbosity_args(parser)

    parser.add_argument("-t", "--target", metavar="TARGET",
                        type=str, default="kc705_dds",
                        help="Target to build, one of: "
                             "kc705_dds kasli sayma_rtm sayma_amc_standalone "
                             "sayma_amc_drtio_master sayma_amc_drtio_satellite")
    parser.add_argument("-H", "--host",
                        type=str, default="lab.m-labs.hk",
                        help="SSH host where the development board is located")
    parser.add_argument('-b', "--board",
                        type=str, default="{boardtype}-1",
                        help="Board to connect to on the development SSH host")
    parser.add_argument("-d", "--device",
                        type=str, default="{board}.{host}",
                        help="Address or domain corresponding to the development board")
    parser.add_argument("-s", "--serial",
                        type=str, default="/dev/ttyUSB_{board}",
                        help="TTY device corresponding to the development board")
    parser.add_argument("-l", "--lockfile",
                        type=str, default="/run/boards/{board}",
                        help="The lockfile to be acquired for the duration of the actions")
    parser.add_argument("-w", "--wait", action="store_true",
                        help="Wait for the board to unlock instead of aborting the actions")

    parser.add_argument("actions", metavar="ACTION",
                        type=str, default=[], nargs="+",
                        help="actions to perform, sequence of: "
                             "build clean reset flash flash+log connect hotswap")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)
    if args.verbose == args.quiet == 0:
        logging.getLogger().setLevel(logging.INFO)

    def build_dir(*path, target=args.target):
        return os.path.join("/tmp", target, *path)

    build_args = []
    if args.target == "kc705_dds":
        boardtype, firmware = "kc705", "runtime"
    elif args.target == "sayma_amc_standalone":
        boardtype, firmware = "sayma_amc", "runtime"
        build_args += ["--rtm-csr-csv", build_dir("sayma_rtm_csr.csv", target="sayma_rtm")]
    elif args.target == "sayma_amc_drtio_master":
        boardtype, firmware = "sayma_amc", "runtime"
    elif args.target == "sayma_amc_drtio_satellite":
        boardtype, firmware = "sayma_amc", "satman"
    elif args.target == "sayma_rtm":
        boardtype, firmware = "sayma_rtm", None
    else:
        raise NotImplementedError("unknown target {}".format(args.target))

    board    = args.board.format(boardtype=boardtype)
    device   = args.device.format(board=board, host=args.host)
    lockfile = args.lockfile.format(board=board)
    serial   = args.serial.format(board=board)

    client = SSHClient(args.host)

    flock_acquired = False
    flock_file = None # GC root
    def lock():
        nonlocal flock_acquired
        nonlocal flock_file

        if not flock_acquired:
            fuser_args = ["fuser", "-u", lockfile]
            fuser = client.spawn_command(fuser_args)
            fuser_file = fuser.makefile('r')
            fuser_match = re.search(r"\((.+?)\)", fuser_file.readline())
            if fuser_match.group(1) == os.getenv("USER"):
                logger.info("Lock already acquired by {}".format(os.getenv("USER")))
                flock_acquired = True
                return

            logger.info("Acquiring device lock")
            flock_args = ["flock"]
            if not args.wait:
                flock_args.append("--nonblock")
            flock_args += ["--verbose", lockfile]
            flock_args += ["sleep", "86400"]

            flock = client.spawn_command(flock_args, get_pty=True)
            flock_file = flock.makefile('r')
            while not flock_acquired:
                line = flock_file.readline()
                if not line:
                    break
                logger.debug(line.rstrip())
                if line.startswith("flock: executing"):
                    flock_acquired = True
                elif line.startswith("flock: failed"):
                    logger.error("Failed to get lock")
                    sys.exit(1)

    def flash(*steps):
        flash_args = ["artiq_flash"]
        for _ in range(args.verbose):
            flash_args.append("-v")
        flash_args += ["-H", args.host, "-t", boardtype]
        flash_args += ["--srcbuild", build_dir()]
        flash_args += ["--preinit-command", "source /var/boards/{}".format(board)]
        flash_args += steps
        subprocess.check_call(flash_args)

    for action in args.actions:
        if action == "build":
            logger.info("Building target")
            try:
                subprocess.check_call([
                    "python3", "-m", "artiq.gateware.targets." + args.target,
                               "--no-compile-gateware",
                               *build_args,
                                "--output-dir", build_dir()])
            except subprocess.CalledProcessError:
                logger.error("Build failed")
                sys.exit(1)

        elif action == "clean":
            logger.info("Cleaning build directory")
            shutil.rmtree(build_dir, ignore_errors=True)

        elif action == "reset":
            lock()

            logger.info("Resetting device")
            flash("start")

        elif action == "flash" or action == "flash+log":
            lock()

            logger.info("Flashing firmware")
            flash("proxy", "bootloader", "firmware")

            logger.info("Booting firmware")
            if action == "flash+log":
                flterm = client.spawn_command(["flterm", serial, "--output-only"])
                flash("start")
                client.drain(flterm)
            else:
                flash("start")

        elif action == "connect":
            lock()

            transport = client.get_transport()
            transport.set_keepalive(30)

            def forwarder(local_stream, remote_stream):
                try:
                    while True:
                        r, _, _ = select.select([local_stream, remote_stream], [], [])
                        if local_stream in r:
                            data = local_stream.recv(65535)
                            if data == b"":
                                break
                            remote_stream.sendall(data)
                        if remote_stream in r:
                            data = remote_stream.recv(65535)
                            if data == b"":
                                break
                            local_stream.sendall(data)
                except Exception as err:
                    logger.error("Cannot forward on port %s: %s", port, repr(err))
                local_stream.close()
                remote_stream.close()

            def listener(port):
                listener = socket.socket()
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(('localhost', port))
                listener.listen(8)
                while True:
                    local_stream, peer_addr = listener.accept()
                    logger.info("Accepting %s:%s and opening SSH channel to %s:%s",
                                *peer_addr, device, port)
                    try:
                        remote_stream = \
                            transport.open_channel('direct-tcpip', (device, port), peer_addr)
                    except Exception:
                        logger.exception("Cannot open channel on port %s", port)
                        continue

                    thread = threading.Thread(target=forwarder, args=(local_stream, remote_stream),
                                              name="forward-{}".format(port), daemon=True)
                    thread.start()

            ports = [1380, 1381, 1382, 1383]
            for port in ports:
                thread = threading.Thread(target=listener, args=(port,),
                                          name="listen-{}".format(port), daemon=True)
                thread.start()

            logger.info("Forwarding ports {} to core device and logs from core device"
                            .format(", ".join(map(str, ports))))
            client.run_command(["flterm", serial, "--output-only"])

        elif action == "hotswap":
            logger.info("Hotswapping firmware")
            try:
                subprocess.check_call(["artiq_coreboot", "hotswap",
                    build_dir("software", firmware, firmware + ".bin")])
            except subprocess.CalledProcessError:
                logger.error("Build failed")
                sys.exit(1)

        else:
            logger.error("Unknown action {}".format(action))
            sys.exit(1)

if __name__ == "__main__":
    main()
