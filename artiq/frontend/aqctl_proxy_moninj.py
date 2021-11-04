#!/usr/bin/env python3

import argparse
import asyncio
import atexit
import logging

from sipyco import common_args
from sipyco.asyncio_tools import atexit_register_coroutine
from sipyco.pc_rpc import Server as RPCServer
from sipyco.sync_struct import Publisher, Notifier, Subscriber

from artiq import __version__ as artiq_version
from artiq.coredevice.comm_moninj import CommMonInj

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Connectable:
    def __init__(self):
        self.connected_event = asyncio.Event()

    async def connect(self, addr, port): raise NotImplementedError

    async def disconnect(self): raise NotImplementedError

    async def on_connected(self):
        self.connected_event.set()

    async def on_disconnected(self):
        self.connected_event.clear()

    @property
    def connected(self):
        return self.connected_event.is_set()


class MonInjCoredev(Connectable):
    def __init__(self, supervisor):
        super().__init__()
        self._supervisor = supervisor
        self.comm = None
        self.init_comm()

    def init_comm(self):
        self.comm = CommMonInj(self.on_monitor, self.on_injection_status, self.on_disconnected)

    async def connect(self, addr, port):
        try:
            logging.info(f"trying to connect to coredev at {addr}:{port}")
            self.init_comm()
            await self.comm.connect(addr, port)
        except asyncio.CancelledError:
            raise
        except:
            logger.error("failed to connect to core device moninj", exc_info=True)
            await asyncio.sleep(10.)
        else:
            await self.on_connected()

    async def disconnect(self):
        if self.connected:
            await self.comm.close()

    @property
    def connected(self):
        return super().connected and hasattr(self.comm, "_writer")

    # Callbacks
    async def on_connected(self):
        if self.connected:
            return

        await super().on_connected()
        logging.info("connected to coredev")
        self._supervisor.notify["connected"]["coredev"] = True

    async def on_disconnected(self):
        if not self.connected:
            return

        await super().on_disconnected()
        logger.error("disconnected from core device")
        self._supervisor.notify["connected"]["coredev"] = False
        while self._supervisor.activation_event.is_set() and not self.connected:
            try:
                await self.connect(self._supervisor.master.core_addr, 1383)
            except:
                logging.error("core device still unreachable, retrying...")
                await asyncio.sleep(10)

    def on_monitor(self, channel, probe, value):
        logger.debug(f"received monitor data {(channel, probe, value)}")
        if channel not in self._supervisor.notify["monitor"].raw_view:
            self._supervisor.notify["monitor"][channel] = dict()
        self._supervisor.notify["monitor"][channel][probe] = value

    def on_injection_status(self, channel, override, value):
        logger.debug(f"received injection status {(channel, override, value)}")
        if channel not in self._supervisor.notify["injection_status"].raw_view:
            self._supervisor.notify["injection_status"][channel] = dict()
        self._supervisor.notify["injection_status"][channel][override] = value


class MonInjMaster(Connectable):
    def __init__(self, supervisor):
        super().__init__()
        self._core_addr_cache = None
        self._supervisor = supervisor
        self.ddb = dict()
        self.ddb_notify = Subscriber(notifier_name="devices", notify_cb=self.on_notify,
                                     target_builder=self.build_ddb, disconnect_cb=self.on_disconnected)

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
        return self.ddb["core"]["arguments"]["host"]

    # Callbacks
    async def on_connected(self):
        if self.connected:
            return

        await super().on_connected()
        logger.info("connected to master")
        self._supervisor.notify["connected"]["master"] = True

        # if the core device address is not the same of what we memoized, notify the change
        if self._core_addr_cache != self.core_addr:
            await self.on_core_addr_changed(self._core_addr_cache, self.core_addr)
            self._core_addr_cache = self.core_addr

        if not self._supervisor.core.connected:
            await self._supervisor.core.connect(self.core_addr, 1383)

    async def on_disconnected(self):
        if not self.connected:
            return

        await super().on_disconnected()
        logger.info("disconnected from master")
        self._supervisor.notify["connected"]["master"] = False
        while self._supervisor.activation_event.is_set() and not self.connected:
            try:
                await self.connect(self._supervisor.master_addr, self._supervisor.master_notify_port)
            except:
                logging.error("master still unreachable, retrying...")
                await asyncio.sleep(10)

    async def on_core_addr_changed(self, old_addr, addr):
        if old_addr and addr:
            logging.debug(f"core address changed, old: {old_addr}, new: {addr}")
            await self._supervisor.core.disconnect()

    async def on_core_change(self, mod):
        if mod["value"]["arguments"]["host"] != self._core_addr_cache:
            await self.on_core_addr_changed(self._core_addr_cache, self.core_addr)
            self._core_addr_cache = self.core_addr

    async def on_notify(self, mod):
        logger.debug(f"received mod from master {mod}")

        if mod["action"] == "init":
            await self.on_connected()

        if mod["action"] == "setitem":
            if mod["key"] == "core":
                await self.on_core_change(mod)


class MonInjSupervisor:
    def __init__(self, master, notify_port):
        self.notify = Notifier({
            # could have used defaultdict for these two, sadly it didn't work
            "monitor": dict(),
            "injection_status": dict(),
            "connected": {"coredev": False, "master": False}
        })
        self.master_addr = master
        self.master_notify_port = notify_port
        self.core, self.master = MonInjCoredev(self), MonInjMaster(self)
        self.activation_event = asyncio.Event()

    async def connect(self):
        logger.debug("starting the subcomponents")
        self.activation_event.set()
        await self.master.connect(self.master_addr, self.master_notify_port)

    async def reconnect(self):
        logger.debug("reconnecting the subcomponents")
        await self.stop()
        await self.connect()

    async def stop(self):
        logger.debug("stopping the subcomponents")
        self.activation_event.clear()
        await self.core.disconnect()
        await self.master.disconnect()

    # RPC methods
    def monitor_probe(self, enable, channel, probe):
        self.core.comm.monitor_probe(enable, channel, probe)

    def monitor_injection(self, enable, channel, overrd):
        self.core.comm.monitor_injection(enable, channel, overrd)

    def inject(self, channel, override, value):
        self.core.comm.inject(channel, override, value)

    def get_injection_status(self, channel, override):
        self.core.comm.get_injection_status(channel, override)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ MonInj Proxy")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")

    group = parser.add_argument_group("master related")
    group.add_argument(
        "--master-addr", type=str, required=True,
        help="hostname or IP of the master to connect to")

    group.add_argument(
        "--master-port-notify", type=int, default=3250,
        help="port to connect to for notification service in master")

    common_args.simple_network_args(parser, [
        ("proxy-core-moninj-pubsub", "data synchronization service for core device moninj", 2383),
        ("proxy-core-moninj-rpc", "remote control service to core device moninj", 2384)
    ])

    return parser


class PingTarget:
    def ping(self):
        return True


def main():
    args = get_argparser().parse_args()
    loop = asyncio.get_event_loop()
    atexit.register(loop.close)
    bind = common_args.bind_address_from_args(args)

    proxy = MonInjSupervisor(args.master_addr, args.master_port_notify)
    proxy_pubsub = Publisher({
        "coredevice": proxy.notify,
    })
    proxy_rpc = RPCServer({
        "proxy": proxy,
        "ping": PingTarget()
    }, allow_parallel=False, builtin_terminate=True)
    loop.run_until_complete(proxy.connect())
    loop.run_until_complete(proxy_pubsub.start(bind, args.port_proxy_core_moninj_pubsub))
    loop.run_until_complete(proxy_rpc.start(bind, args.port_proxy_core_moninj_rpc))

    atexit_register_coroutine(proxy_pubsub.stop)
    atexit_register_coroutine(proxy_rpc.stop)
    atexit_register_coroutine(proxy.stop)

    logger.info("ARTIQ Core Device MonInj Proxy is now ready.")
    loop.run_forever()


if __name__ == "__main__":
    main()
