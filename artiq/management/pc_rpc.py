"""
This module provides a remote procedure call (RPC) mechanism over sockets
between conventional computers (PCs) running Python. It strives to be
transparent and uses ``artiq.management.pyon`` internally so that e.g. Numpy
arrays can be easily used.

"""

import socket
import asyncio
import traceback

from artiq.management import pyon


class RemoteError(Exception):
    """Exception raised when a RPC failed or raised an exception on the
    remote (server) side.

    """
    pass


class Client:
    """This class proxies the methods available on the server so that they
    can be used as if they were local methods.

    For example, if the server provides method ``foo``, and ``c`` is a local
    ``Client`` object, then the method can be called as: ::

        result = c.foo(param1, param2)

    The parameters and the result are automatically transferred with the
    server.

    Only methods are supported. Attributes must be accessed by providing and
    using "get" and/or "set" methods on the server side.

    At object initialization, the connection to the remote server is
    automatically attempted. The user must call ``close_rpc`` to
    free resources properly after initialization completes successfully.

    :param host: Identifier of the server. The string can represent a
        hostname or a IPv4 or IPv6 address (see
        ``socket.create_connection`` in the Python standard library).
    :param port: TCP port to use.

    """
    def __init__(self, host, port):
        self.socket = socket.create_connection((host, port))

    def close_rpc(self):
        """Closes the connection to the RPC server.

        No further method calls should be done after this method is called.

        """
        self.socket.close()

    def _do_rpc(self, name, args, kwargs):
        obj = {"action": "call", "name": name, "args": args, "kwargs": kwargs}
        line = pyon.encode(obj) + "\n"
        self.socket.sendall(line.encode())

        buf = self.socket.recv(4096).decode()
        while "\n" not in buf:
            more = self.socket.recv(4096)
            if not more:
                break
            buf += more.decode()
        obj = pyon.decode(buf)
        if obj["result"] == "ok":
            return obj["ret"]
        elif obj["result"] == "error":
            raise RemoteError(obj["message"] + "\n" + obj["traceback"])
        else:
            raise ValueError

    def __getattr__(self, name):
        def proxy(*args, **kwargs):
            return self._do_rpc(name, args, kwargs)
        return proxy


class Server:
    """This class creates a TCP server that handles requests coming from
    ``Client`` objects.

    The server is designed using ``asyncio`` so that it can easily support
    multiple connections without the locking issues that arise in
    multi-threaded applications. Multiple connection support is useful even in
    simple cases: it allows new connections to be be accepted even when the
    previous client failed to properly shut down its connection.

    :param target: Object providing the RPC methods to be exposed to the
        client.

    """
    def __init__(self, target):
        self.target = target
        self._client_tasks = set()

    @asyncio.coroutine
    def start(self, host, port):
        """Starts the server.

        The user must call ``stop`` to free resources properly after this
        method completes successfully.

        This method is a `coroutine`.

        :param host: Bind address of the server (see ``asyncio.start_server``
            from the Python standard library).
        :param port: TCP port to bind to.

        """
        self.server = yield from asyncio.start_server(self._handle_connection,
                                                      host, port)

    @asyncio.coroutine
    def stop(self):
        """Stops the server.

        """
        for task in self._client_tasks:
            task.cancel()
        self.server.close()
        yield from self.server.wait_closed()
        del self.server

    def _client_done(self, task):
        self._client_tasks.remove(task)

    def _handle_connection(self, reader, writer):
        task = asyncio.Task(self._handle_connection_task(reader, writer))
        self._client_tasks.add(task)
        task.add_done_callback(self._client_done)

    @asyncio.coroutine
    def _handle_connection_task(self, reader, writer):
        try:
            while True:
                line = yield from reader.readline()
                if not line:
                    break
                obj = pyon.decode(line.decode())
                action = obj["action"]
                if action == "call":
                    try:
                        method = getattr(self.target, obj["name"])
                        ret = method(*obj["args"], **obj["kwargs"])
                        obj = {"result": "ok", "ret": ret}
                    except Exception as e:
                        obj = {"result": "error",
                               "message": type(e).__name__ + ": " + str(e),
                               "traceback": traceback.format_exc()}
                    line = pyon.encode(obj) + "\n"
                    writer.write(line.encode())
        finally:
            writer.close()


class WaitQuit:
    """Provides facilities to handle the termination of servers.

    Server targets typically inherit from this class, with the method ``quit``
    called via RPC.

    """
    def __init__(self):
        self.terminate_notify = asyncio.Semaphore(0)

    @asyncio.coroutine
    def wait_quit(self):
        """Waits until the `quit` method is called. This is typically used to
        keep the `asyncio` loop running until the server is requested to
        terminate.

        This method is a `coroutine`.

        """
        yield from self.terminate_notify.acquire()

    def quit(self):
        """Quits the server.

        """
        self.terminate_notify.release()
