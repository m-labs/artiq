#!/usr/bin/env python3

import argparse
import logging
import asyncio
import struct
from enum import Enum

from sipyco.asyncio_tools import AsyncioServer, SignalHandler
from sipyco.pc_rpc import Server
from sipyco import common_args

from artiq.coredevice.comm_moninj import CommMonInj


logger = logging.getLogger(__name__)


class EventType(Enum):
    PROBE = 0
    INJECTION = 1


class MonitorMux:
    def __init__(self):
        self.listeners = dict()
        self.comm_moninj = None

    def _monitor(self, listener, event):
        try:
            listeners = self.listeners[event]
        except KeyError:
            listeners = []
            self.listeners[event] = listeners
            if event[0] == EventType.PROBE:
                logger.debug("starting monitoring channel %d probe %d", event[1], event[2])
                self.comm_moninj.monitor_probe(True, event[1], event[2])
            elif event[0] == EventType.INJECTION:
                logger.debug("starting monitoring channel %d injection %d", event[1], event[2])
                self.comm_moninj.monitor_injection(True, event[1], event[2])
            else:
                raise ValueError
        if listener in listeners:
            logger.warning("listener trying to subscribe twice to %s", event)
        else:
            listeners.append(listener)

    def _unmonitor(self, listener, event):
        try:
            listeners = self.listeners[event]
        except KeyError:
            listeners = []
        try:
            listeners.remove(listener)
        except ValueError:
            logger.warning("listener trying to unsubscribe from %s, but was not subscribed", event)
            return
        if not listeners:
            del self.listeners[event]
            if event[0] == EventType.PROBE:
                logger.debug("stopped monitoring channel %d probe %d", event[1], event[2])
                self.comm_moninj.monitor_probe(False, event[1], event[2])
            elif event[0] == EventType.INJECTION:
                logger.debug("stopped monitoring channel %d injection %d", event[1], event[2])
                self.comm_moninj.monitor_injection(False, event[1], event[2])
            else:
                raise ValueError

    def monitor_probe(self, listener, enable, channel, probe):
        if enable:
            self._monitor(listener, (EventType.PROBE, channel, probe))
        else:
            self._unmonitor(listener, (EventType.PROBE, channel, probe))

    def monitor_injection(self, listener, enable, channel, overrd):
        if enable:
            self._monitor(listener, (EventType.INJECTION, channel, overrd))
        else:
            self._unmonitor(listener, (EventType.INJECTION, channel, overrd))

    def _event_cb(self, event, value):
        try:
            listeners = self.listeners[event]
        except KeyError:
            # We may still receive buffered events shortly after an unsubscription. They can be ignored.
            logger.debug("received event %s but no listener", event)
            listeners = []
        for listener in listeners:
            if event[0] == EventType.PROBE:
                listener.monitor_cb(event[1], event[2], value)
            elif event[0] == EventType.INJECTION:
                listener.injection_status_cb(event[1], event[2], value)
            else:
                raise ValueError

    def monitor_cb(self, channel, probe, value):
        self._event_cb((EventType.PROBE, channel, probe), value)

    def injection_status_cb(self, channel, override, value):
        self._event_cb((EventType.INJECTION, channel, override), value)

    def remove_listener(self, listener):
        for event, listeners in list(self.listeners.items()):
            try:
                listeners.remove(listener)
            except ValueError:
                pass
            if not listeners:
                del self.listeners[event]
                if event[0] == EventType.PROBE:
                    logger.debug("stopped monitoring channel %d probe %d", event[1], event[2])
                    self.comm_moninj.monitor_probe(False, event[1], event[2])
                elif event[0] == EventType.INJECTION:
                    logger.debug("stopped monitoring channel %d injection %d", event[1], event[2])
                    self.comm_moninj.monitor_injection(False, event[1], event[2])
                else:
                    raise ValueError

    def disconnect_cb(self):
        self.listeners.clear()


class ProxyConnection:
    def __init__(self, monitor_mux, reader, writer):
        self.monitor_mux = monitor_mux
        self.reader = reader
        self.writer = writer

    async def handle(self):
        try:
            while True:
                ty = await self.reader.read(1)
                if not ty:
                    return
                if ty == b"\x00":     # MonitorProbe
                    packet = await self.reader.readexactly(6)
                    enable, channel, probe = struct.unpack("<blb", packet)
                    self.monitor_mux.monitor_probe(self, enable, channel, probe)
                elif ty == b"\x01":   # Inject
                    packet = await self.reader.readexactly(6)
                    channel, overrd, value = struct.unpack("<lbb", packet)
                    self.monitor_mux.comm_moninj.inject(channel, overrd, value)
                elif ty == b"\x02":   # GetInjectionStatus
                    packet = await self.reader.readexactly(5)
                    channel, overrd = struct.unpack("<lb", packet)
                    self.monitor_mux.comm_moninj.get_injection_status(channel, overrd)
                elif ty == b"\x03":   # MonitorInjection
                    packet = await self.reader.readexactly(6)
                    enable, channel, overrd = struct.unpack("<blb", packet)
                    self.monitor_mux.monitor_injection(self, enable, channel, overrd)
                else:
                    raise ValueError
        finally:
            self.monitor_mux.remove_listener(self)

    def monitor_cb(self, channel, probe, value):
        packet = struct.pack("<blbq", 0, channel, probe, value)
        self.writer.write(packet)

    def injection_status_cb(self, channel, override, value):
        packet = struct.pack("<blbb", 1, channel, override, value)
        self.writer.write(packet)


class ProxyServer(AsyncioServer):
    def __init__(self, monitor_mux):
        AsyncioServer.__init__(self)
        self.monitor_mux = monitor_mux

    async def _handle_connection_cr(self, reader, writer):
        line = await reader.readline()
        if line != b"ARTIQ moninj\n":
            logger.error("incorrect magic")
            return
        await ProxyConnection(self.monitor_mux, reader, writer).handle()


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ moninj proxy")
    common_args.verbosity_args(parser)
    common_args.simple_network_args(parser, [
        ("proxy", "proxying", 1383),
        ("control", "control", 1384)
    ])
    parser.add_argument("core_addr", metavar="CORE_ADDR",
                        help="hostname or IP address of the core device")
    return parser


class PingTarget:
    def ping(self):
        return True


def main():
    args = get_argparser().parse_args()
    common_args.init_logger_from_args(args)

    bind_address = common_args.bind_address_from_args(args)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        signal_handler = SignalHandler()
        signal_handler.setup()
        try:
            monitor_mux = MonitorMux()
            comm_moninj = CommMonInj(monitor_mux.monitor_cb,
                                     monitor_mux.injection_status_cb,
                                     monitor_mux.disconnect_cb)
            monitor_mux.comm_moninj = comm_moninj
            loop.run_until_complete(comm_moninj.connect(args.core_addr))
            try:
                proxy_server = ProxyServer(monitor_mux)
                loop.run_until_complete(proxy_server.start(bind_address, args.port_proxy))
                try:
                    server = Server({"moninj_proxy": PingTarget()}, None, True)
                    loop.run_until_complete(server.start(bind_address, args.port_control))
                    try:
                        _, pending = loop.run_until_complete(asyncio.wait(
                            [signal_handler.wait_terminate(),
                             server.wait_terminate(),
                             comm_moninj.wait_terminate()],
                            return_when=asyncio.FIRST_COMPLETED))
                        for task in pending:
                            task.cancel()
                    finally:
                        loop.run_until_complete(server.stop())
                finally:
                    loop.run_until_complete(proxy_server.stop())
            finally:
                loop.run_until_complete(comm_moninj.close())
        finally:
            signal_handler.teardown()
    finally:
        loop.close()


if __name__ == "__main__":
    main()
