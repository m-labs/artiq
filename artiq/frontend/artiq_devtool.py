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

from artiq.tools import verbosity_args, init_logger, logger, SSHClient


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ core device development tool")

    verbosity_args(parser)

    parser.add_argument("-t", "--target", metavar="TARGET",
                        type=str, default="kc705_dds",
                        help="Target to build, one of: "
                             "kc705_dds kasli sayma_rtm sayma_amc_standalone "
                             "sayma_amc_drtio_master sayma_amc_drtio_satellite")
    parser.add_argument("-H", "--host", metavar="HOSTNAME",
                        type=str, default="lab.m-labs.hk",
                        help="SSH host where the development board is located")
    parser.add_argument('-b', "--board", metavar="BOARD",
                        type=str, default=None,
                        help="Board to connect to on the development SSH host")
    parser.add_argument("-d", "--device", metavar="DEVICENAME",
                        type=str, default="{board}.{hostname}",
                        help="Address or domain corresponding to the development board")
    parser.add_argument("-s", "--serial", metavar="SERIAL",
                        type=str, default="/dev/ttyUSB_{board}",
                        help="TTY device corresponding to the development board")
    parser.add_argument("-l", "--lockfile", metavar="LOCKFILE",
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

    build_args = []
    if args.target == "kc705_dds":
        boardtype, firmware = "kc705", "runtime"
    elif args.target == "sayma_amc_standalone":
        boardtype, firmware = "sayma", "runtime"
        build_args += ["--rtm-csr-csv", "/tmp/sayma_rtm/sayma_rtm_csr.csv"]
    elif args.target == "sayma_amc_drtio_master":
        boardtype, firmware = "sayma", "runtime"
    elif args.target == "sayma_amc_drtio_satellite":
        boardtype, firmware = "sayma", "satman"
    elif args.target == "sayma_rtm":
        boardtype, firmware = "sayma_rtm", None
    else:
        raise NotImplementedError("unknown target {}".format(args.target))

    flash_args = ["-t", boardtype]
    if boardtype == "sayma":
        if args.board is None:
            args.board = "sayma-1"
        if args.board == "sayma-1":
            flash_args += ["--preinit-command", "ftdi_location 5:2"]
        elif args.board == "sayma-2":
            flash_args += ["--preinit-command", "ftdi_location 3:10"]
        elif args.board == "sayma-3":
            flash_args += ["--preinit-command", "ftdi_location 5:1"]
        else:
            raise NotImplementedError("unknown --preinit-command for {}".format(boardtype))

    client = SSHClient(args.host)
    substs = {
        "target":     args.target,
        "hostname":   args.host,
        "boardtype":  boardtype,
        "board":      args.board if args.board else boardtype + "-1",
        "firmware":   firmware,
    }
    substs.update({
        "devicename": args.device.format(**substs),
        "lockfile":   args.lockfile.format(**substs),
        "serial":     args.serial.format(**substs),
    })

    flock_acquired = False
    flock_file = None # GC root
    def lock():
        nonlocal flock_acquired
        nonlocal flock_file

        if not flock_acquired:
            logger.info("Acquiring device lock")
            flock = client.spawn_command("flock --verbose {block} {lockfile} sleep 86400"
                                            .format(block="" if args.wait else "--nonblock",
                                                    **substs),
                                         get_pty=True)
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

    def artiq_flash(args, synchronous=True):
        args = flash_args + args
        args = ["'{}'".format(arg) if " " in arg else arg for arg in args]
        cmd = client.spawn_command(
            "artiq_flash " + " ".join(args),
            **substs)
        if synchronous:
            client.drain(cmd)
        else:
            return cmd

    for action in args.actions:
        if action == "build":
            logger.info("Building target")
            try:
                subprocess.check_call(["python3",
                                        "-m", "artiq.gateware.targets." + args.target,
                                        "--no-compile-gateware",
                                        *build_args,
                                        "--output-dir",
                                        "/tmp/{target}".format(**substs)])
            except subprocess.CalledProcessError:
                logger.error("Build failed")
                sys.exit(1)

        elif action == "clean":
            logger.info("Cleaning build directory")
            target_dir = "/tmp/{target}".format(**substs)
            if os.path.isdir(target_dir):
                shutil.rmtree(target_dir)

        elif action == "reset":
            logger.info("Resetting device")
            artiq_flash(["reset"])

        elif action == "flash" or action == "flash+log":
            def upload_product(product, ext):
                logger.info("Uploading {}".format(product))
                client.get_sftp().put("/tmp/{target}/software/{product}/{product}.{ext}"
                                          .format(target=args.target, product=product, ext=ext),
                                      "{tmp}/{product}.{ext}"
                                          .format(tmp=client.tmp, product=product, ext=ext))

            upload_product("bootloader", "bin")
            upload_product(firmware, "fbi")

            logger.info("Flashing firmware")
            artiq_flash(["-d", "{tmp}", "proxy", "bootloader", "firmware",
                         "start" if action == "flash" else ""])

            if action == "flash+log":
                logger.info("Booting firmware")
                flterm = client.spawn_command(
                    "flterm {serial} " +
                    "--kernel {tmp}/{firmware}.bin " +
                    ("--upload-only" if action == "boot" else "--output-only"),
                    **substs)
                artiq_flash(["start"], synchronous=False)
                client.drain(flterm)

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
                                *peer_addr, args.device, port)
                    try:
                        remote_stream = \
                            transport.open_channel('direct-tcpip', (args.device, port), peer_addr)
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
            client.run_command(
                "flterm {serial} --output-only",
                **substs)

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
