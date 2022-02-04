#!/usr/bin/env python3

import argparse
import asyncio
import atexit
import logging
import struct
from collections import defaultdict

from sipyco import common_args
from sipyco.asyncio_tools import atexit_register_coroutine, AsyncioServer
from sipyco.pc_rpc import Server as RPCServer
from sipyco.sync_struct import Subscriber

from artiq import __version__ as artiq_version
from artiq.coredevice.comm_moninj import CommMonInj

logger = logging.getLogger(__name__)


class _Client:
    def __init__(self, reader, writer):
        self.probe = set()
        self.injection = set()
        self.reader = reader
        self.writer = writer

    async def read_format(self, fmt):
        data = await self.reader.readexactly(struct.calcsize(fmt))
        return struct.unpack(fmt, data)

    def write_monitor_status(self, channel, probe, value, endian):
        # MonitorStatus
        packet = struct.pack(endian + "blbl", 0, channel, probe, value)
        self.writer.write(packet)

    def write_injection_status(self, channel, override, value, endian):
        # InjectionStatus
        packet = struct.pack(endian + "blbb", 1, channel, override, value)
        self.writer.write(packet)


class _MonitoredFieldInfo:
    def __init__(self):
        self.refs = 0
        self.value = None


class _MonitoredField:
    def __init__(self):
        self.probe = defaultdict(_MonitoredFieldInfo)
        self.injection = defaultdict(_MonitoredFieldInfo)


class MonInjCoredev:
    def __init__(self, proxy):
        self.proxy = proxy
        self.comm = None
        self._connected = False
        self.connector_task = None
        self.connection_event = asyncio.Event()

    async def connector(self, addr, port):
        while True:
            await self.connection_event.wait()
            self.connection_event.clear()
            try:
                logger.info(f"trying to connect to coredev at {addr}:{port}")
                comm = CommMonInj(self.on_monitor, self.on_injection_status,
                                  self.on_disconnected)
                await comm.connect(addr, port)
            except asyncio.CancelledError:
                logger.debug("core connection task is cancelled")
                break
            except:
                logger.error("core device is unreachable, retrying...",
                             exc_info=True)
                await asyncio.sleep(10.)
                self.connection_event.set()
            else:
                self.comm = comm
                await self.on_connected()

    async def connect(self, addr, port):
        if self.connector_task:
            await self.disconnect()
        self.connector_task = asyncio.ensure_future(self.connector(addr, port))
        self.connection_event.set()

    async def disconnect(self):
        try:
            if self.connector_task:
                self.connector_task.cancel()
                await self.connector_task
                self.connector_task = None
        except asyncio.CancelledError:
            pass
        if self.comm:
            await self.comm.close()
            self.comm = None
        self.on_disconnected()

    @property
    def connected(self):
        return self._connected and hasattr(self.comm, "_writer")

    @connected.setter
    def connected(self, value):
        self._connected = value

    # Callbacks
    async def on_connected(self):
        if not self.connected:
            self.connected = True
            logger.info("connected to core device")
            for (channel, probe) in self.proxy.mon_fields.probe.keys():
                self.comm.monitor_probe(True, channel, probe)
            for (channel, overrd) in self.proxy.mon_fields.injection.keys():
                self.comm.monitor_injection(True, channel, overrd)

    def on_disconnected(self):
        if self.connected:
            self.connected = False
            logger.info("disconnected from core device")
            while self.connector_task and not self.connection_event.is_set():
                self.connection_event.set()

    def on_monitor(self, channel, probe, value):
        logger.debug(f"received monitor data {(channel, probe, value)}")
        self.proxy.mon_fields.probe[(channel, probe)].value = value
        for client in self.proxy.clients:
            if (channel, probe) in client.probe:
                client.write_monitor_status(channel, probe, value,
                                            self.comm.endian)

    def on_injection_status(self, channel, override, value):
        logger.debug(f"received injection status {(channel, override, value)}")
        self.proxy.mon_fields.injection[(channel, override)].value = value
        for client in self.proxy.clients:
            if (channel, override) in client.injection:
                client.write_injection_status(channel, override, value,
                                              self.comm.endian)


class MonInjMaster:
    def __init__(self, proxy):
        self._core_addr = None
        self.proxy = proxy
        self.ddb = dict()
        self.ddb_notify = Subscriber("devices", self.build_ddb, self.on_notify,
                                     self.on_disconnected)
        self.connected = False
        self.connector_task = None
        self.connection_event = asyncio.Event()

    def build_ddb(self, init):
        self.ddb = init
        return self.ddb

    async def connector(self, master, port):
        while True:
            await self.connection_event.wait()
            self.connection_event.clear()
            logger.debug(
                f"trying to connect to master server at {master}:{port}")
            try:
                await self.ddb_notify.connect(master, port)
            except asyncio.CancelledError:
                logger.debug("master connection task is cancelled")
                break
            except:
                logger.error("master is unreachable, retrying...")
                await asyncio.sleep(10.)
                self.connection_event.set()

    async def connect(self, master, port):
        if self.connector_task:
            await self.disconnect()
        self.connector_task = asyncio.ensure_future(
            self.connector(master, port))
        self.connection_event.set()

    async def disconnect(self):
        try:
            if self.connector_task:
                self.connector_task.cancel()
                await self.connector_task
                self.connector_task = None
        except asyncio.CancelledError:
            pass
        if self.ddb_notify:
            await self.ddb_notify.close()
            self.ddb_notify = None
        self.on_disconnected()

    @property
    def core_addr(self):
        return self._core_addr

    async def set_core_addr(self, value):
        if self._core_addr and value and self._core_addr != value:
            logger.debug(
                f"core address changed, old: {self._core_addr}, new: {value}")
            await self.proxy.core.disconnect()
        self._core_addr = value

    # Callbacks
    async def on_connected(self):
        if not self.connected:
            self.connected = True
            logger.info("connected to master")
            await self.set_core_addr(self.ddb["core"]["arguments"]["host"])
            if not self.proxy.core.connected:
                await self.proxy.core.connect(self.core_addr, 1383)

    def on_disconnected(self):
        if self.connected:
            self.connected = False
            logger.info("disconnected from master")
            while self.connector_task and not self.connection_event.is_set():
                self.connection_event.set()

    async def on_notify(self, mod):
        logger.debug(f"received mod from master {mod}")
        if mod["action"] == "init":
            await self.on_connected()
        if mod["action"] == "setitem" and mod["key"] == "core":
            await self.set_core_addr(mod["value"]["arguments"]["host"])


class MonInjProxy(AsyncioServer):
    def __init__(self, master, notify_port):
        super().__init__()
        self.master_addr = master
        self.master_notify_port = notify_port
        self.core, self.master = MonInjCoredev(self), MonInjMaster(self)
        self.active = False
        self.mon_fields = _MonitoredField()
        self.clients = set()

    async def connect(self):
        logger.debug("starting the proxy")
        await self.master.connect(self.master_addr, self.master_notify_port)
        self.active = True

    async def reconnect(self):
        logger.debug("reconnecting the proxy")
        await self.stop()
        await self.connect()

    async def stop(self):
        logger.debug("stopping the proxy")
        self.active = False
        await super().stop()
        await asyncio.wait(
            [self.core.disconnect(), self.master.disconnect()])

    async def _handle_connection_cr(self, reader, writer):
        line = await reader.readline()
        if line == b"ARTIQ moninj\n":
            return await self._handle_moninj_connection_cr(reader, writer)
        return

    async def _handle_moninj_connection_cr(self, reader, writer):
        remote_addr = writer.get_extra_info('peername')
        logger.info("client connected (remote: %s)", remote_addr)
        writer.write(b"e" if self.core.comm.endian == "<" else b"E")
        client = _Client(reader, writer)
        self.clients.add(client)
        try:
            for (channel, probe), v in self.mon_fields.probe.items():
                client.write_monitor_status(channel, probe, v.value,
                                            self.core.comm.endian)
            for (channel, overrd), v in self.mon_fields.injection.items():
                client.write_injection_status(channel, overrd, v.value,
                                              self.core.comm.endian)
            while True:
                opcode = await reader.read(1)
                if not opcode:
                    break
                while not self.core.connected:
                    await asyncio.sleep(0)
                if opcode == b"\x00":
                    enable, channel, probe = await client.read_format(
                        self.core.comm.endian + "blb")
                    logger.debug(
                        f"received MonitorProbe {(enable, channel, probe)}"
                    )
                    self.update_probe(enable, channel, probe,
                                      client=client)
                elif opcode == b"\x01":
                    channel, override, value = await client.read_format(
                        self.core.comm.endian + "lbb")
                    logger.debug(
                        f"received Inject {(channel, override, value)}")
                    self.core.comm.inject(channel, override, value)
                elif opcode == b"\x02":
                    channel, override = await client.read_format(
                        self.core.comm.endian + "lb")
                    logger.debug(
                        f"received GetInjectionStatus {(channel, override)}")
                    self.core.comm.get_injection_status(channel, override)
                elif opcode == b"\x03":
                    enable, channel, overrd = await client.read_format(
                        self.core.comm.endian + "blb")
                    logger.debug(
                        f"received MonitorInjection {(enable, channel, overrd)}")
                    self.update_injection(enable, channel, overrd,
                                          client=client)
                else:
                    raise ValueError("Unknown packet type", opcode)
        except:
            logger.error("Error occurred during connection loop",
                         exc_info=True)
        finally:
            for (channel, probe) in client.probe:
                self.update_probe(False, channel, probe)
            for (channel, overrd) in client.injection:
                self.update_injection(False, channel, overrd)
            self.clients.remove(client)
            logger.info("client disconnected (remote: %s)", remote_addr)

    def update_probe(self, enable, channel, probe, client=None):
        commit_monitor = False
        field = self.mon_fields.probe[(channel, probe)]
        if enable:
            if client:
                client.probe.add((channel, probe))
            commit_monitor = field.refs == 0
            field.refs += 1
        elif (channel, probe) in self.mon_fields.probe:
            if client:
                client.probe.remove((channel, probe))
            if field.refs <= 1:
                commit_monitor = True
                del self.mon_fields.probe[(channel, probe)]
            else:
                field.refs -= 1
        if commit_monitor:
            logger.debug(
                f"committing monitor probe {(enable, channel, probe)}")
            self.core.comm.monitor_probe(enable, channel, probe)

    def update_injection(self, enable, channel, overrd, client=None):
        commit_monitor = False
        field = self.mon_fields.injection[(channel, overrd)]
        if enable:
            if client:
                client.injection.add((channel, overrd))
            commit_monitor = field.refs == 0
            field.refs += 1
        elif (channel, overrd) in self.mon_fields.injection:
            if client:
                client.injection.remove((channel, overrd))
            if field.refs == 1:
                commit_monitor = True
                del self.mon_fields.injection[(channel, overrd)]
            else:
                field.refs -= 1
        if commit_monitor:
            logger.debug(
                f"committing monitor injection {(enable, channel, overrd)}")
            self.core.comm.monitor_injection(enable, channel, overrd)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ Core Device Monitor/Injection Proxy")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")
    common_args.verbosity_args(parser)
    parser.add_argument(
        "--bind", default=[], action="append",
        help="additional hostname or IP address to bind to; "
             "use '*' to bind to all interfaces (default: %(default)s)")
    parser.add_argument(
        "--no-localhost-bind", default=False, action="store_true",
        help="do not implicitly also bind to localhost addresses")

    group = parser.add_argument_group("master related")
    group.add_argument(
        "--master-addr", type=str, required=True,
        help="hostname or IP of the master to connect to")

    group.add_argument(
        "--master-port-notify", type=int, default=3250,
        help="port to connect to for notification service in master")

    group = parser.add_argument_group("proxy server")
    group.add_argument(
        "--port-proxy", default=2383, type=int,
        help="TCP port for proxy to listen to (default: 2383)")
    group.add_argument(
        "--port-rpc", default=2384, type=int,
        help="TCP port for RPC heartbeat to listen to (default: 2384)")
    return parser


class PingTarget:
    def ping(self):
        return True


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)
    loop = asyncio.get_event_loop()
    atexit.register(loop.close)
    bind = common_args.bind_address_from_args(args)

    proxy = MonInjProxy(args.master_addr, args.master_port_notify)
    proxy_rpc = RPCServer({"ping": PingTarget()}, builtin_terminate=True)
    loop.run_until_complete(proxy.connect())
    loop.run_until_complete(proxy.start(bind, args.port_proxy))
    loop.run_until_complete(proxy_rpc.start(bind, args.port_rpc))

    atexit_register_coroutine(proxy_rpc.stop)
    atexit_register_coroutine(proxy.stop)

    print("ARTIQ Core Device MonInj Proxy is now ready.")
    loop.run_forever()


if __name__ == "__main__":
    main()
