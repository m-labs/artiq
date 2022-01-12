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

logging.basicConfig(level=logging.INFO)
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

    async def connect(self, addr, port):
        try:
            logging.info(f"trying to connect to coredev at {addr}:{port}")
            comm = CommMonInj(self.on_monitor, self.on_injection_status,
                              self.on_disconnected)
            await comm.connect(addr, port)
        except asyncio.CancelledError:
            raise
        except:
            logger.error("failed to connect to core device moninj",
                         exc_info=True)
            await asyncio.sleep(10.)
        else:
            self.comm = comm
            await self.on_connected()

    async def disconnect(self):
        if self.connected:
            await self.comm.close()
            self.comm = None

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
            logging.info("connected to core device")

    async def on_disconnected(self):
        if self.connected:
            self.connected = False
            logger.info("disconnected from core device")
            while self.proxy.active and not self.connected:
                try:
                    await self.connect(self.proxy.master.core_addr, 1383)
                except:
                    logging.error("core device still unreachable, retrying...")
                    await asyncio.sleep(10)

    def on_monitor(self, channel, probe, value):
        logger.debug(f"received monitor data {(channel, probe, value)}")
        self.proxy.mon_fields.probe[(channel, probe)].value = value
        for client in self.proxy.clients:
            # MonitorStatus
            packet = struct.pack(self.comm.endian + "blbl", 0, channel, probe,
                                 value)
            client.writer.write(packet)

    def on_injection_status(self, channel, override, value):
        logger.debug(f"received injection status {(channel, override, value)}")
        self.proxy.mon_fields.injection[(channel, override)].value = value
        for client in self.proxy.clients:
            if (channel, override) in client.injection:
                # InjectionStatus
                packet = struct.pack(self.comm.endian + "blbb", 1, channel,
                                     override, value)
                client.writer.write(packet)


class MonInjMaster:
    def __init__(self, proxy):
        self._core_addr = None
        self.proxy = proxy
        self.ddb = dict()
        self.ddb_notify = Subscriber("devices", self.build_ddb, self.on_notify,
                                     self.on_disconnected)
        self.connected = False

    def build_ddb(self, init):
        self.ddb = init
        return self.ddb

    async def connect(self, master, port):
        logger.debug(f"trying to connect to master server at {master}:{port}")
        await self.ddb_notify.connect(master, port)

    async def disconnect(self):
        await self.ddb_notify.close()
        await self.on_disconnected()

    @property
    def core_addr(self):
        return self._core_addr

    async def set_core_addr(self, value):
        if self._core_addr and value and self._core_addr != value:
            logging.debug(
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

    async def on_disconnected(self):
        if self.connected:
            self.connected = False
            logger.info("disconnected from master")
            while self.proxy.active and not self.connected:
                try:
                    await self.connect(self.proxy.master_addr,
                                       self.proxy.master_notify_port)
                except:
                    logging.error("master still unreachable, retrying...")
                    await asyncio.sleep(10)

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
        self.clients = []

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
        await asyncio.wait(
            [self.core.disconnect(), self.master.disconnect(), super().stop()])

    async def _handle_connection_cr(self, reader, writer):
        if await reader.readline() == b"ARTIQ moninj\n":
            logger.info("client connected (remote: %s)",
                        writer.get_extra_info('peername'))
            writer.write(b"e")
            client, client_idx = _Client(reader, writer), len(self.clients)
            self.clients.append(client)
            try:
                for (channel, overrd), v in self.mon_fields.injection.items():
                    packet = struct.pack(self.core.comm.endian + "blbb", 1,
                                         channel, overrd, v.value)
                    client.writer.write(packet)

                while True:
                    opcode = await reader.read(1)
                    if not opcode:
                        break
                    if opcode == b"\x00":
                        enable, channel, probe = await client.read_format(
                            self.endian + "blb")
                        logger.debug(
                            f"received MonitorProbe {(enable, channel, probe)}"
                        )
                        self.update_probe(enable, channel, probe,
                                          client=client)
                    elif opcode == b"\x01":
                        channel, override, value = await client.read_format(
                            self.endian + "lbb")
                        logger.debug(
                            f"received Inject {(channel, override, value)}")
                        self.core.comm.inject(channel, override, value)
                    elif opcode == b"\x02":
                        channel, override = await client.read_format(
                            self.endian + "lb")
                        logger.debug(
                            f"received GetInjectionStatus {(channel, override)}")
                        self.core.comm.get_injection_status(channel, override)
                    elif opcode == b"\x03":
                        enable, channel, overrd = await client.read_format(
                            self.endian + "blb")
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
                self.clients.pop(client_idx)
                logger.info("client disconnected (remote: %s)",
                            writer.get_extra_info('peername'))

    def update_probe(self, enable, channel, probe, client=None):
        commit_monitor = False
        if enable:
            if client:
                client.probe.add((channel, probe))
            commit_monitor = self.mon_fields.probe[(channel, probe)].refs == 0
            self.mon_fields.probe[(channel, probe)].refs += 1
        elif (channel, probe) in self.mon_fields.probe:
            if client:
                client.probe.remove((channel, probe))
            if self.mon_fields.probe[(channel, probe)].refs <= 1:
                commit_monitor = True
                del self.mon_fields.probe[(channel, probe)]
            else:
                self.mon_fields.probe[(channel, probe)].refs -= 1
        if commit_monitor:
            logger.debug(
                f"committing monitor probe {(enable, channel, probe)}")
            self.core.comm.monitor_probe(enable, channel, probe)

    def update_injection(self, enable, channel, overrd, client=None):
        commit_monitor = False
        if enable:
            if client:
                client.injection.add((channel, overrd))
            commit_monitor = self.mon_fields.injection[
                                 (channel, overrd)].refs == 0
            self.mon_fields.injection[(channel, overrd)].refs += 1
        elif (channel, overrd) in self.mon_fields.injection:
            if client:
                client.injection.remove((channel, overrd))
            if self.mon_fields.injection[(channel, overrd)].refs == 1:
                commit_monitor = True
                del self.mon_fields.injection[(channel, overrd)]
            else:
                self.mon_fields.injection[(channel, overrd)].refs -= 1
        if commit_monitor:
            logger.debug(
                f"committing monitor injection {(enable, channel, overrd)}")
            self.core.comm.monitor_injection(enable, channel, overrd)

    @property
    def endian(self):
        return self.core.comm.endian if self.core.comm else None


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ Core Device Monitor/Injection Proxy")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")
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
    group.add_argument("--port-proxy", default=2383, type=int,
                       help="TCP port for proxy to listen to (default: 2383)")
    group.add_argument("--port-rpc", default=2384, type=int,
                       help="TCP port for RPC heartbeat to listen to (default: 2384)")
    return parser


class PingTarget:
    def ping(self):
        return True


def main():
    args = get_argparser().parse_args()
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

    logger.info("ARTIQ Core Device MonInj Proxy is now ready.")
    loop.run_forever()


if __name__ == "__main__":
    main()
