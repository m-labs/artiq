#!/usr/bin/env python3

import asyncio
import atexit
import argparse
import os
import logging
import shlex
import socket

from artiq.protocols.sync_struct import Subscriber
from artiq.protocols.pc_rpc import AsyncioClient, Server
from artiq.tools import verbosity_args, init_logger
from artiq.tools import TaskObject, asyncio_process_wait_timeout, Condition


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
        "--bind", default="::1",
        help="hostname or IP address to bind to")
    parser.add_argument(
        "--bind-port", default=3249, type=int,
        help="TCP port to listen to for control (default: %(default)d)")
    return parser


class Controller:
    def __init__(self, name, ddb_entry):
        self.name = name
        self.command = ddb_entry["command"]
        self.retry_timer = ddb_entry.get("retry_timer", 5)
        self.retry_timer_backoff = ddb_entry.get("retry_timer_backoff", 1.1)

        self.host = ddb_entry["host"]
        self.port = ddb_entry["port"]
        self.ping_timer = ddb_entry.get("ping_timer", 30)
        self.ping_timeout = ddb_entry.get("ping_timeout", 30)
        self.term_timeout = ddb_entry.get("term_timeout", 30)

        self.retry_timer_cur = self.retry_timer
        self.retry_now = Condition()
        self.process = None
        self.launch_task = asyncio.Task(self.launcher())

    @asyncio.coroutine
    def end(self):
        self.launch_task.cancel()
        yield from asyncio.wait_for(self.launch_task, None)

    @asyncio.coroutine
    def _call_controller(self, method):
        remote = AsyncioClient()
        yield from remote.connect_rpc(self.host, self.port, None)
        try:
            targets, _ = remote.get_rpc_id()
            remote.select_rpc_target(targets[0])
            r = yield from getattr(remote, method)()
        finally:
            remote.close_rpc()
        return r

    @asyncio.coroutine
    def _ping(self):
        try:
            ok = yield from asyncio.wait_for(self._call_controller("ping"),
                                             self.ping_timeout)
            if ok:
                self.retry_timer_cur = self.retry_timer
            return ok
        except:
            return False

    @asyncio.coroutine
    def _wait_and_ping(self):
        while True:
            try:
                yield from asyncio_process_wait_timeout(self.process,
                                                        self.ping_timer)
            except asyncio.TimeoutError:
                logger.debug("pinging controller %s", self.name)
                ok = yield from self._ping()
                if not ok:
                    logger.warning("Controller %s ping failed", self.name)
                    yield from self._terminate()
                    return
            else:
                break

    @asyncio.coroutine
    def launcher(self):
        try:
            while True:
                logger.info("Starting controller %s with command: %s",
                            self.name, self.command)
                try:
                    self.process = yield from asyncio.create_subprocess_exec(
                        *shlex.split(self.command))
                    yield from self._wait_and_ping()
                except FileNotFoundError:
                    logger.warning("Controller %s failed to start", self.name)
                else:
                    logger.warning("Controller %s exited", self.name)
                logger.warning("Restarting in %.1f seconds",
                               self.retry_timer_cur)
                try:
                    yield from asyncio.wait_for(self.retry_now.wait(),
                                                self.retry_timer_cur)
                except asyncio.TimeoutError:
                    pass
                self.retry_timer_cur *= self.retry_timer_backoff
        except asyncio.CancelledError:
            yield from self._terminate()

    @asyncio.coroutine
    def _terminate(self):
        logger.info("Terminating controller %s", self.name)
        if self.process is not None and self.process.returncode is None:
            try:
                yield from asyncio.wait_for(self._call_controller("terminate"),
                                            self.term_timeout)
            except:
                logger.warning("Controller %s did not respond to terminate "
                               "command, killing", self.name)
                self.process.kill()
            try:
                yield from asyncio_process_wait_timeout(self.process,
                                                        self.term_timeout)
            except:
                logger.warning("Controller %s failed to exit, killing",
                               self.name)
                self.process.kill()
                yield from self.process.wait()
        logger.debug("Controller %s terminated", self.name)


def get_ip_addresses(host):
    try:
        addrinfo = socket.getaddrinfo(host, None)
    except:
        return set()
    return {info[4][0] for info in addrinfo}


class Controllers:
    def __init__(self):
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
                k, ddb_entry = param
                if k in self.active:
                    yield from self.active[k].end()
                self.active[k] = Controller(k, ddb_entry)
            elif action == "del":
                yield from self.active[param].end()
                del self.active[param]
            else:
                raise ValueError

    def __setitem__(self, k, v):
        if (isinstance(v, dict) and v["type"] == "controller"
                and self.host_filter in get_ip_addresses(v["host"])):
            v["command"] = v["command"].format(name=k,
                                               bind=self.host_filter,
                                               port=v["port"])
            self.queue.put_nowait(("set", (k, v)))
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
    def __init__(self):
        self.current_controllers = Controllers()

    def set_host_filter(self, host_filter):
        self.current_controllers.host_filter = host_filter

    def sync_struct_init(self, init):
        if self.current_controllers is not None:
            self.current_controllers.delete_all()
        for k, v in init.items():
            self.current_controllers[k] = v
        return self.current_controllers


class ControllerManager(TaskObject):
    def __init__(self, server, port, retry_master):
        self.server = server
        self.port = port
        self.retry_master = retry_master
        self.controller_db = ControllerDB()

    @asyncio.coroutine
    def _do(self):
        try:
            subscriber = Subscriber("devices",
                                    self.controller_db.sync_struct_init)
            while True:
                try:
                    def set_host_filter():
                        s = subscriber.writer.get_extra_info("socket")
                        localhost = s.getsockname()[0]
                        self.controller_db.set_host_filter(localhost)
                    yield from subscriber.connect(self.server, self.port,
                                                  set_host_filter)
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
                logger.warning("Retrying in %.1f seconds", self.retry_master)
                yield from asyncio.sleep(self.retry_master)
        except asyncio.CancelledError:
            pass
        finally:
            yield from self.controller_db.current_controllers.shutdown()

    def retry_now(self, k):
        """If a controller is disabled and pending retry, perform that retry
        now."""
        self.controller_db.current_controllers.active[k].retry_now.notify()


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    if os.name == "nt":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    atexit.register(lambda: loop.close())

    ctlmgr = ControllerManager(args.server, args.port, args.retry_master)
    ctlmgr.start()
    atexit.register(lambda: loop.run_until_complete(ctlmgr.stop()))

    class CtlMgrRPC:
        retry_now = ctlmgr.retry_now

    rpc_target = CtlMgrRPC()
    rpc_server = Server({"ctlmgr": rpc_target}, builtin_terminate=True)
    loop.run_until_complete(rpc_server.start(args.bind, args.bind_port))
    atexit.register(lambda: loop.run_until_complete(rpc_server.stop()))

    loop.run_until_complete(rpc_server.wait_terminate())


if __name__ == "__main__":
    main()
