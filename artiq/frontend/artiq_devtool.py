#!/usr/bin/env python3

# This script makes the following assumptions:
#  * miniconda is installed remotely at ~/miniconda
#  * misoc and artiq are installed remotely via conda

import sys
import argparse
import subprocess
import socket
import select
import threading
import paramiko
import os
import shutil

from artiq.tools import verbosity_args, init_logger, logger
from random import Random


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device "
                                                 "development tool")

    verbosity_args(parser)

    parser.add_argument("--host", metavar="HOST",
                        type=str, default="lab.m-labs.hk",
                        help="SSH host where the development board is located")
    parser.add_argument("-s", "--serial", metavar="SERIAL",
                        type=str, default="/dev/ttyUSB_kc705",
                        help="TTY device corresponding to the development board")
    parser.add_argument("-i", "--ip", metavar="IP",
                        type=str, default="kc705.lab.m-labs.hk",
                        help="IP address corresponding to the development board")
    parser.add_argument("-t", "--target", metavar="TARGET",
                        type=str, default="kc705_dds",
                        help="Target to build, one of: "
                             "kc705_dds kc705_drtio_master kc705_drtio_satellite")
    parser.add_argument("-c", "--config", metavar="TARGET_CFG",
                        type=str, default="openocd-kc705.cfg",
                        help="OpenOCD configuration file corresponding to the development board")

    parser.add_argument("actions", metavar="ACTION",
                        type=str, default=[], nargs="+",
                        help="actions to perform, sequence of: "
                             "build reset boot boot+log connect hotswap clean")

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    if args.target == "kc705_dds" or args.target == "kc705_drtio_master":
        firmware = "runtime"
    elif args.target == "kc705_drtio_satellite":
        firmware = "satman"
    else:
        raise NotImplementedError("unknown target {}".format(args.target))

    ssh = None
    def get_ssh():
        nonlocal ssh
        if ssh is not None:
            return ssh
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(args.host)
        return ssh

    sftp = None
    def get_sftp():
        nonlocal sftp
        if sftp is not None:
            return sftp
        sftp = get_ssh().open_sftp()
        return sftp

    rng = Random()
    tmp = "artiq" + "".join([rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(6)])
    env = "bash -c 'export PATH=$HOME/miniconda/bin:$PATH; exec $0 $*' "

    def run_command(cmd, **kws):
        logger.info("Executing {}".format(cmd))
        chan = get_ssh().get_transport().open_session()
        chan.set_combine_stderr(True)
        chan.exec_command(cmd.format(tmp=tmp, env=env, serial=args.serial, ip=args.ip,
                                     firmware=firmware, **kws))
        return chan.makefile()

    def drain(chan):
        while True:
            char = chan.read(1)
            if char == b"":
                break
            sys.stderr.write(char.decode("utf-8", errors='replace'))

    for action in args.actions:
        if action == "build":
            logger.info("Building firmware")
            try:
                subprocess.check_call(["python3",
                                        "-m", "artiq.gateware.targets." + args.target,
                                        "--no-compile-gateware",
                                        "--output-dir",
                                        "/tmp/{target}".format(target=args.target)])
            except subprocess.CalledProcessError:
                logger.error("Build failed")
                sys.exit(1)

        elif action == "clean":
            logger.info("Cleaning build directory")
            target_dir = "/tmp/{target}".format(target=args.target)
            if os.path.isdir(target_dir):
                shutil.rmtree(target_dir)

        elif action == "reset":
            logger.info("Resetting device")
            artiq_flash = run_command(
                "{env} artiq_flash start" +
                (" --target-file " + args.config if args.config else ""))
            drain(artiq_flash)

        elif action == "boot" or action == "boot+log":
            logger.info("Uploading firmware")
            get_sftp().mkdir("/tmp/{tmp}".format(tmp=tmp))
            get_sftp().put("/tmp/{target}/software/{firmware}/{firmware}.bin"
                                .format(target=args.target, firmware=firmware),
                           "/tmp/{tmp}/{firmware}.bin".format(tmp=tmp, firmware=firmware))

            logger.info("Booting firmware")
            flterm = run_command(
                "{env} python3 flterm.py {serial} " +
                "--kernel /tmp/{tmp}/{firmware}.bin " +
                ("--upload-only" if action == "boot" else "--output-only"))
            artiq_flash = run_command(
                "{env} artiq_flash start" +
                (" --target-file " + args.config if args.config else ""))
            drain(flterm)

        elif action == "connect":
            def forwarder(port):
                listener = socket.socket()
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(('localhost', port))
                listener.listen(1)
                while True:
                    local_stream, peer_addr = listener.accept()
                    logger.info("Accepting %s:%s and opening SSH channel to %s:%s",
                                *peer_addr, args.ip, port)
                    if get_ssh().get_transport() is None:
                        logger.error("Trying to open a channel before the transport is ready!")
                        continue

                    try:
                        remote_stream = get_ssh().get_transport() \
                            .open_channel('direct-tcpip', (args.ip, port), peer_addr)
                    except Exception as e:
                        logger.exception("Cannot open channel on port %s", port)
                        continue
                    while True:
                        try:
                            r, w, x = select.select([local_stream, remote_stream], [], [])
                            if local_stream in r:
                                data = local_stream.recv(1024)
                                if data == b"":
                                    break
                                remote_stream.send(data)
                            if remote_stream in r:
                                data = remote_stream.recv(1024)
                                if data == b"":
                                    break
                                local_stream.send(data)
                        except Exception as e:
                            logger.exception("Forward error on port %s", port)
                    local_stream.close()
                    remote_stream.close()

            for port in (1380, 1381, 1382):
                thread = threading.Thread(target=forwarder, args=(port,),
                                          name="port-{}".format(port), daemon=True)
                thread.start()

            logger.info("Connecting to device")
            flterm = run_command(
                "{env} python3 flterm.py {serial} --output-only")
            drain(flterm)

        elif action == "hotswap":
            logger.info("Hotswapping firmware")
            try:
                subprocess.check_call(["python3",
                    "-m", "artiq.frontend.artiq_coreboot", "hotswap",
                    "/tmp/{target}/software/{firmware}/{firmware}.bin"
                        .format(target=args.target, firmware=firmware)])
            except subprocess.CalledProcessError:
                logger.error("Build failed")
                sys.exit(1)

        else:
            logger.error("Unknown action {}".format(action))
            sys.exit(1)

if __name__ == "__main__":
    main()
