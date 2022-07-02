import asyncio
import logging
import struct
from enum import Enum

from sipyco.keepalive import async_open_connection

__all__ = ["TTLProbe", "TTLOverride", "CommMonInj"]


logger = logging.getLogger(__name__)


class TTLProbe(Enum):
    level = 0
    oe = 1


class TTLOverride(Enum):
    en = 0
    level = 1
    oe = 2


class CommMonInj:
    def __init__(self, monitor_cb, injection_status_cb, disconnect_cb=None):
        self.monitor_cb = monitor_cb
        self.injection_status_cb = injection_status_cb
        self.disconnect_cb = disconnect_cb

    async def connect(self, host, port=1383):
        self._reader, self._writer = await async_open_connection(
            host,
            port,
            after_idle=1,
            interval=1,
            max_fails=3,
        )

        try:
            self._writer.write(b"ARTIQ moninj\n")
            self._receive_task = asyncio.ensure_future(self._receive_cr())
        except:
            self._writer.close()
            del self._reader
            del self._writer
            raise

    def wait_terminate(self):
        return self._receive_task

    async def close(self):
        self.disconnect_cb = None
        try:
            self._receive_task.cancel()
            try:
                await asyncio.wait_for(self._receive_task, None)
            except asyncio.CancelledError:
                pass
        finally:
            self._writer.close()
            del self._reader
            del self._writer

    def monitor_probe(self, enable, channel, probe):
        packet = struct.pack("<bblb", 0, enable, channel, probe)
        self._writer.write(packet)

    def monitor_injection(self, enable, channel, overrd):
        packet = struct.pack("<bblb", 3, enable, channel, overrd)
        self._writer.write(packet)

    def inject(self, channel, override, value):
        packet = struct.pack("<blbb", 1, channel, override, value)
        self._writer.write(packet)

    def get_injection_status(self, channel, override):
        packet = struct.pack("<blb", 2, channel, override)
        self._writer.write(packet)

    async def _receive_cr(self):
        try:
            while True:
                ty = await self._reader.read(1)
                if not ty:
                    return
                if ty == b"\x00":
                    payload = await self._reader.readexactly(13)
                    channel, probe, value = struct.unpack("<lbq", payload)
                    self.monitor_cb(channel, probe, value)
                elif ty == b"\x01":
                    payload = await self._reader.readexactly(6)
                    channel, override, value = struct.unpack("<lbb", payload)
                    self.injection_status_cb(channel, override, value)
                else:
                    raise ValueError("Unknown packet type", ty)
        except asyncio.CancelledError:
            raise
        except:
            logger.error("Moninj connection terminating with exception", exc_info=True)
        finally:
            if self.disconnect_cb is not None:
                self.disconnect_cb()
