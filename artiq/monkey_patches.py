import sys


__all__ = []


if sys.version_info[:2] == (3, 5) and sys.version_info[2] in (2, 3):
    import asyncio

    # See https://github.com/m-labs/artiq/issues/506
    def _ipaddr_info(host, port, family, type, proto):
        return None
    asyncio.base_events._ipaddr_info = _ipaddr_info
