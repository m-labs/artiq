import sys


__all__ = []


if sys.version_info[:3] == (3, 5, 1):
    import asyncio
    import socket
    import collections
    import itertools
    import os

    # See https://github.com/m-labs/artiq/issues/253
    @asyncio.coroutines.coroutine
    def create_server(self, protocol_factory, host=None, port=None,
                      *,
                      family=socket.AF_UNSPEC,
                      flags=socket.AI_PASSIVE,
                      sock=None,
                      backlog=100,
                      ssl=None,
                      reuse_address=None,
                      reuse_port=None):
        """Create a TCP server.
        The host parameter can be a string, in that case the TCP server is bound
        to host and port.
        The host parameter can also be a sequence of strings and in that case
        the TCP server is bound to all hosts of the sequence. If a host
        appears multiple times (possibly indirectly e.g. when hostnames
        resolve to the same IP address), the server is only bound once to that
        host.
        Return a Server object which can be used to stop the service.
        This method is a coroutine.
        """
        if isinstance(ssl, bool):
            raise TypeError('ssl argument must be an SSLContext or None')
        if host is not None or port is not None:
            if sock is not None:
                raise ValueError(
                    'host/port and sock can not be specified at the same time')

            AF_INET6 = getattr(socket, 'AF_INET6', 0)
            if reuse_address is None:
                reuse_address = os.name == 'posix' and sys.platform != 'cygwin'
            sockets = []
            if host == '':
                hosts = [None]
            elif (isinstance(host, str) or
                  not isinstance(host, collections.Iterable)):
                hosts = [host]
            else:
                hosts = host

            fs = [self._create_server_getaddrinfo(host, port, family=family,
                                                  flags=flags)
                  for host in hosts]
            infos = yield from asyncio.tasks.gather(*fs, loop=self)
            infos = set(itertools.chain.from_iterable(infos))

            completed = False
            try:
                for res in infos:
                    af, socktype, proto, canonname, sa = res
                    try:
                        sock = socket.socket(af, socktype, proto)
                    except socket.error:
                        # Assume it's a bad family/type/protocol combination.
                        if self._debug:
                            asyncio.log.logger.warning('create_server() failed to create '
                                           'socket.socket(%r, %r, %r)',
                                           af, socktype, proto, exc_info=True)
                        continue
                    sockets.append(sock)
                    if reuse_address:
                        sock.setsockopt(
                            socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
                    if reuse_port:
                        if not hasattr(socket, 'SO_REUSEPORT'):
                            raise ValueError(
                                'reuse_port not supported by socket module')
                        else:
                            sock.setsockopt(
                                socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
                    # Disable IPv4/IPv6 dual stack support (enabled by
                    # default on Linux) which makes a single socket
                    # listen on both address families.
                    if af == AF_INET6 and hasattr(socket, 'IPPROTO_IPV6'):
                        sock.setsockopt(socket.IPPROTO_IPV6,
                                        socket.IPV6_V6ONLY,
                                        True)
                    try:
                        sock.bind(sa)
                    except OSError as err:
                        raise OSError(err.errno, 'error while attempting '
                                      'to bind on address %r: %s'
                                      % (sa, err.strerror.lower()))
                completed = True
            finally:
                if not completed:
                    for sock in sockets:
                        sock.close()
        else:
            if sock is None:
                raise ValueError('Neither host/port nor sock were specified')
            sockets = [sock]

        server = asyncio.base_events.Server(self, sockets)
        for sock in sockets:
            sock.listen(backlog)
            sock.setblocking(False)
            self._start_serving(protocol_factory, sock, ssl, server)
        if self._debug:
            asyncio.log.logger.info("%r is serving", server)
        return server

    asyncio.base_events.BaseEventLoop.create_server = create_server


    # See https://github.com/m-labs/artiq/issues/247
    def _loop_writing(self, f=None, data=None):
        try:
            assert f is self._write_fut
            self._write_fut = None
            self._pending_write = 0
            if f:
                f.result()
            if data is None:
                data = self._buffer
                self._buffer = None
            if not data:
                if self._closing:
                    self._loop.call_soon(self._call_connection_lost, None)
                if self._eof_written:
                    self._sock.shutdown(socket.SHUT_WR)
                # Now that we've reduced the buffer size, tell the
                # protocol to resume writing if it was paused.  Note that
                # we do this last since the callback is called immediately
                # and it may add more data to the buffer (even causing the
                # protocol to be paused again).
                self._maybe_resume_protocol()
            else:
                self._write_fut = self._loop._proactor.send(self._sock, data)
                if not self._write_fut.done():
                    assert self._pending_write == 0
                    self._pending_write = len(data)
                    self._write_fut.add_done_callback(self._loop_writing)
                    self._maybe_pause_protocol()
                else:
                    self._write_fut.add_done_callback(self._loop_writing)
        except (ConnectionResetError, ConnectionAbortedError) as exc:
            self._force_close(exc)
        except OSError as exc:
            self._fatal_error(exc, 'Fatal write error on pipe transport')
    
    from asyncio import proactor_events
    proactor_events._ProactorBaseWritePipeTransport._loop_writing = _loop_writing


if sys.version_info[:3] == (3, 5, 2):
    import asyncio

    # See https://github.com/m-labs/artiq/issues/506
    def _ipaddr_info(host, port, family, type, proto):
        return None
    asyncio.base_events._ipaddr_info = _ipaddr_info
