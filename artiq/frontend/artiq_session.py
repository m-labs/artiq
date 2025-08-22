#!/usr/bin/env python3

import asyncio
import os
import argparse
import sys
import subprocess
import signal
from artiq import __version__ as artiq_version


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ session manager. "
                    "Automatically runs the master, dashboard and "
                    "local controller manager on the current machine. "
                    "The latter requires the ``artiq-comtools`` package to "
                    "be installed.")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")
    parser.add_argument("-m", action="append", default=[],
                        help="add argument to the master command line")
    parser.add_argument("-c", action="append", default=[],
                        help="add argument to the controller manager command line")
    parser.add_argument("-d", action="append", default=[],
                        help="add argument to the dashboard command line")

    return parser


# process creation flags for using clean_process_term()
if os.name == "nt":
    process_creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
else:
    process_creationflags = 0


async def clean_process_term(process):
    if os.name != "nt":
        process.terminate()
    else:
        process.send_signal(signal.CTRL_BREAK_EVENT)
    await process.wait()


async def forward_process_stream(name, stream):
    while True:
        line = (await stream.readline()).decode()
        if not line:
            break
        sys.stdout.write("<" + name + "> " + line)


async def main_task(master_cmd, ctlmgr_cmd, dashboard_cmd):
    print("<session> starting master")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    master = await asyncio.create_subprocess_exec(
        *master_cmd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, creationflags=process_creationflags)
    forward_master_stdout_task = None  # outer scope to delay task GC
    forward_master_stderr_task = None
    try:
        forward_master_stderr = asyncio.create_task(
            forward_process_stream("master", master.stderr))
        line = ""
        while line.rstrip("\r\n") != "ARTIQ master is now ready.":
            line = (await master.stdout.readline()).decode()
            if not line:
                print("<session> master failed to start, exiting.")
                return
            sys.stdout.write("<master> " + line)
        forward_master_stdout_task = asyncio.create_task(
            forward_process_stream("master", master.stdout))

        print("<session> starting controller manager")
        ctlmgr = await asyncio.create_subprocess_exec(
            *ctlmgr_cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, creationflags=process_creationflags)
        forward_ctlmgr_stdout_task = None  # outer scope to delay task GC
        forward_ctlmgr_stderr_task = None
        try:
            forward_master_stdout_task = asyncio.create_task(
                forward_process_stream("ctlmgr", ctlmgr.stdout))
            forward_master_stderr_task = asyncio.create_task(
                forward_process_stream("ctlmgr", ctlmgr.stderr))
            await asyncio.sleep(1.5)  # wait for moninj controller to start. FIXME: actually check controller status
            print("<session> starting dashboard")
            dashboard = await asyncio.create_subprocess_exec(*dashboard_cmd,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env)
            forward_dashboard_stdout_task = asyncio.create_task(
                forward_process_stream("dashboard", dashboard.stdout))
            forward_master_stderr_task = asyncio.create_task(
                forward_process_stream("dashboard", dashboard.stderr))
            await dashboard.wait()
            print("<session> dashboard exited, terminating...")
        finally:
            print("<session> waiting for controller manager to exit")
            await clean_process_term(ctlmgr)
    finally:
        print("<session> waiting for master to exit")
        await clean_process_term(master)


def main():
    args = get_argparser().parse_args()

    master_cmd    = [sys.executable, "-u", "-m", "artiq.frontend.artiq_master"]
    ctlmgr_cmd    = [sys.executable,       "-m", "artiq_comtools.artiq_ctlmgr"]
    dashboard_cmd = [sys.executable,       "-m", "artiq.frontend.artiq_dashboard"]
    master_cmd    += args.m
    ctlmgr_cmd    += args.c
    dashboard_cmd += args.d

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main_task(master_cmd, ctlmgr_cmd, dashboard_cmd))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
