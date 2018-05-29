import sys
import socket


__all__ = []


if sys.version_info[:3] >= (3, 5, 2):
    import asyncio

    # See https://github.com/m-labs/artiq/issues/506
    def _ipaddr_info(host, port, family, type, proto):
        return None
    asyncio.base_events._ipaddr_info = _ipaddr_info

    # See https://github.com/m-labs/artiq/issues/1016
    @asyncio.coroutine
    def sock_connect(self, sock, address):
        """Connect to a remote socket at address.

        This method is a coroutine.
        """
        if self._debug and sock.gettimeout() != 0:
            raise ValueError("the socket must be non-blocking")

        if not hasattr(socket, 'AF_UNIX') or sock.family != socket.AF_UNIX:
            socktype = sock.type & 0xf  # WA https://bugs.python.org/issue21327
            resolved = asyncio.base_events._ensure_resolved(
                address, family=sock.family, type=socktype, proto=sock.proto, loop=self)
            if not resolved.done():
                yield from resolved
            _, _, _, _, address = resolved.result()[0]

        fut = self.create_future()
        self._sock_connect(fut, sock, address)
        return (yield from fut)
    asyncio.selector_events.BaseSelectorEventLoop.sock_connect = sock_connect
