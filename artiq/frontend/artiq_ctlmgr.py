#!/usr/bin/env python3

import asyncio
import argparse
import os
import logging
import signal
import shlex
import socket

from artiq.protocols.sync_struct import Subscriber
from artiq.tools import verbosity_args, init_logger


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller manager")
    verbosity_args(parser)
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to")
    parser.add_argument(
        "--port", default=3250, type=int,
        help="TCP port to use to connect to the master")
    parser.add_argument(
        "--retry-master", default=5.0, type=float,
        help="retry timer for reconnecting to master")
    parser.add_argument(
        "--retry-command", default=5.0, type=float,
        help="retry timer for restarting a controller command")
    return parser


class Controller:
    def __init__(self, name, command, retry):
        self.launch_task = asyncio.Task(self.launcher(name, command, retry))

    @asyncio.coroutine
    def end(self):
        self.launch_task.cancel()
        yield from asyncio.wait_for(self.launch_task, None)

    @asyncio.coroutine
    def launcher(self, name, command, retry):
        process = None
        try:
            while True:
                logger.info("Starting controller %s with command: %s",
                            name, command)
                try:
                    process = yield from asyncio.create_subprocess_exec(
                        *shlex.split(command))
                    yield from asyncio.shield(process.wait())
                except FileNotFoundError:
                    logger.warning("Controller %s failed to start", name)
                else:
                    logger.warning("Controller %s exited", name)
                logger.warning("Restarting in %.1f seconds", retry)
                yield from asyncio.sleep(retry)
        except asyncio.CancelledError:
            logger.info("Terminating controller %s", name)
            if process is not None and process.returncode is None:
                process.send_signal(signal.SIGTERM)
                logger.debug("Signal sent")
                try:
                    yield from asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Controller %s did not respond to SIGTERM",
                                   name)
                    process.send_signal(signal.SIGKILL)


def get_ip_addresses(host):
    try:
        addrinfo = socket.getaddrinfo(host, None)
    except:
        return set()
    return {info[4][0] for info in addrinfo}


class Controllers:
    def __init__(self, retry_command):
        self.retry_command = retry_command
        self.host_filter = None
        self.active_or_queued = set()
        self.queue = asyncio.Queue()
        self.active = dict()
        self.process_task = asyncio.Task(self._process())

    @asyncio.coroutine
    def _process(self):
        while True:
            action, param = yield from self.queue.get()
            if action == "set":
                k, command = param
                if k in self.active:
                    yield from self.active[k].end()
                self.active[k] = Controller(k, command, self.retry_command)
            elif action == "del":
                yield from self.active[param].end()
                del self.active[param]
            else:
                raise ValueError

    def __setitem__(self, k, v):
        if (isinstance(v, dict) and v["type"] == "controller"
                and self.host_filter in get_ip_addresses(v["host"])):
            command = v["command"].format(name=k,
                                          bind=self.host_filter,
                                          port=v["port"])
            self.queue.put_nowait(("set", (k, command)))
            self.active_or_queued.add(k)

    def __delitem__(self, k):
        if k in self.active_or_queued:
            self.queue.put_nowait(("del", k))
            self.active_or_queued.remove(k)

    def delete_all(self):
        for name in set(self.active_or_queued):
            del self[name]

    @asyncio.coroutine
    def shutdown(self):
        self.process_task.cancel()
        for c in self.active.values():
            yield from c.end()


class ControllerDB:
    def __init__(self, retry_command):
        self.current_controllers = Controllers(retry_command)

    def set_host_filter(self, host_filter):
        self.current_controllers.host_filter = host_filter

    def sync_struct_init(self, init):
        if self.current_controllers is not None:
            self.current_controllers.delete_all()
        for k, v in init.items():
            self.current_controllers[k] = v
        return self.current_controllers


@asyncio.coroutine
def ctlmgr(server, port, retry_master, retry_command):
    controller_db = ControllerDB(retry_command)
    try:
        subscriber = Subscriber("devices", controller_db.sync_struct_init)
        while True:
            try:
                def set_host_filter():
                    s = subscriber.writer.get_extra_info("socket")
                    localhost = s.getsockname()[0]
                    controller_db.set_host_filter(localhost)
                yield from subscriber.connect(server, port, set_host_filter)
                try:
                    yield from asyncio.wait_for(subscriber.receive_task, None)
                finally:
                    yield from subscriber.close()
            except (ConnectionAbortedError, ConnectionError,
                    ConnectionRefusedError, ConnectionResetError) as e:
                logger.warning("Connection to master failed (%s: %s)",
                    e.__class__.__name__, str(e))
            else:
                logger.warning("Connection to master lost")
            logger.warning("Retrying in %.1f seconds", retry_master)
            yield from asyncio.sleep(retry_master)
    except asyncio.CancelledError:
        pass
    finally:
        yield from controller_db.current_controllers.shutdown()


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    try:
        task = asyncio.Task(ctlmgr(
            args.server, args.port, args.retry_master, args.retry_command))
        try:
            loop.run_forever()
        finally:
            task.cancel()
            loop.run_until_complete(asyncio.wait_for(task, None))

    finally:
        loop.close()

if __name__ == "__main__":
    main()
