import asyncio
import logging
import subprocess
import shlex
import socket
import os

from artiq.protocols.sync_struct import Subscriber
from artiq.protocols.pc_rpc import AsyncioClient
from artiq.protocols.logging import LogParser
from artiq.tools import Condition, TaskObject


logger = logging.getLogger(__name__)


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
        self.launch_task = asyncio.ensure_future(self.launcher())

    async def end(self):
        self.launch_task.cancel()
        await asyncio.wait_for(self.launch_task, None)

    async def call(self, method, *args, **kwargs):
        remote = AsyncioClient()
        await remote.connect_rpc(self.host, self.port, None)
        try:
            targets, _ = remote.get_rpc_id()
            await remote.select_rpc_target(targets[0])
            r = await getattr(remote, method)(*args, **kwargs)
        finally:
            remote.close_rpc()
        return r

    async def _ping(self):
        try:
            ok = await asyncio.wait_for(self.call("ping"),
                                        self.ping_timeout)
            if ok:
                self.retry_timer_cur = self.retry_timer
            return ok
        except:
            return False

    async def _wait_and_ping(self):
        while True:
            try:
                await asyncio.wait_for(self.process.wait(),
                                       self.ping_timer)
            except asyncio.TimeoutError:
                logger.debug("pinging controller %s", self.name)
                ok = await self._ping()
                if not ok:
                    logger.warning("Controller %s ping failed", self.name)
                    await self._terminate()
                    return
            else:
                break

    def _get_log_source(self):
        return "controller({})".format(self.name)

    async def launcher(self):
        try:
            while True:
                logger.info("Starting controller %s with command: %s",
                            self.name, self.command)
                try:
                    env = os.environ.copy()
                    env["PYTHONUNBUFFERED"] = "1"
                    self.process = await asyncio.create_subprocess_exec(
                        *shlex.split(self.command),
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        env=env, start_new_session=True)
                    asyncio.ensure_future(
                        LogParser(self._get_log_source).stream_task(
                            self.process.stdout))
                    asyncio.ensure_future(
                        LogParser(self._get_log_source).stream_task(
                            self.process.stderr))
                    await self._wait_and_ping()
                except FileNotFoundError:
                    logger.warning("Controller %s failed to start", self.name)
                else:
                    logger.warning("Controller %s exited", self.name)
                logger.warning("Restarting in %.1f seconds",
                               self.retry_timer_cur)
                try:
                    await asyncio.wait_for(self.retry_now.wait(),
                                           self.retry_timer_cur)
                except asyncio.TimeoutError:
                    pass
                self.retry_timer_cur *= self.retry_timer_backoff
        except asyncio.CancelledError:
            await self._terminate()

    async def _terminate(self):
        if self.process is None or self.process.returncode is not None:
            logger.info("Controller %s already terminated", self.name)
            return
        logger.debug("Terminating controller %s", self.name)
        try:
            await asyncio.wait_for(self.call("terminate"), self.term_timeout)
            await asyncio.wait_for(self.process.wait(), self.term_timeout)
            logger.info("Controller %s terminated", self.name)
            return
        except:
            logger.warning("Controller %s did not exit on request, "
                           "ending the process", self.name)
        if os.name != "nt":
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self.process.wait(), self.term_timeout)
                logger.info("Controller process %s terminated", self.name)
                return
            except asyncio.TimeoutError:
                logger.warning("Controller process %s did not terminate, "
                               "killing", self.name)
        try:
            self.process.kill()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(self.process.wait(), self.term_timeout)
            logger.info("Controller process %s killed", self.name)
            return
        except asyncio.TimeoutError:
            logger.warning("Controller process %s failed to die", self.name)


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
        self.process_task = asyncio.ensure_future(self._process())

    async def _process(self):
        while True:
            action, param = await self.queue.get()
            if action == "set":
                k, ddb_entry = param
                if k in self.active:
                    await self.active[k].end()
                self.active[k] = Controller(k, ddb_entry)
            elif action == "del":
                await self.active[param].end()
                del self.active[param]
            self.queue.task_done()
            if action not in ("set", "del"):
                raise ValueError

    def __setitem__(self, k, v):
        if (isinstance(v, dict) and v["type"] == "controller" and
                self.host_filter in get_ip_addresses(v["host"])):
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

    async def shutdown(self):
        self.process_task.cancel()
        for c in self.active.values():
            await c.end()


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

    async def _do(self):
        try:
            subscriber = Subscriber("devices",
                                    self.controller_db.sync_struct_init)
            while True:
                try:
                    def set_host_filter():
                        s = subscriber.writer.get_extra_info("socket")
                        localhost = s.getsockname()[0]
                        self.controller_db.set_host_filter(localhost)
                    await subscriber.connect(self.server, self.port,
                                             set_host_filter)
                    try:
                        await asyncio.wait_for(subscriber.receive_task, None)
                    finally:
                        await subscriber.close()
                except (ConnectionAbortedError, ConnectionError,
                        ConnectionRefusedError, ConnectionResetError) as e:
                    logger.warning("Connection to master failed (%s: %s)",
                                   e.__class__.__name__, str(e))
                else:
                    logger.warning("Connection to master lost")
                logger.warning("Retrying in %.1f seconds", self.retry_master)
                await asyncio.sleep(self.retry_master)
        except asyncio.CancelledError:
            pass
        finally:
            await self.controller_db.current_controllers.shutdown()

    def retry_now(self, k):
        """If a controller is disabled and pending retry, perform that retry
        now."""
        self.controller_db.current_controllers.active[k].retry_now.notify()
