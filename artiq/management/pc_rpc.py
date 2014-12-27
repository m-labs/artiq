"""
This module provides a remote procedure call (RPC) mechanism over sockets
between conventional computers (PCs) running Python. It strives to be
transparent and uses ``artiq.management.pyon`` internally so that e.g. Numpy
arrays can be easily used.

Note that the server operates on copies of objects provided by the client,
and modifications to mutable types are not written back. For example, if the
client passes a list as a parameter of an RPC method, and that method
``append()s`` an element to the list, the element is not appended to the
client's list.

"""

import socket
import asyncio
import traceback

from artiq.management import pyon
from artiq.management.network import AsyncioServer


class RemoteError(Exception):
    """Raised when a RPC failed or raised an exception on the remote (server)
    side.

    """
    pass


class IncompatibleServer(Exception):
    """Raised by the client when attempting to connect to a server that does
    not have the expected type.

    """
    pass


_init_string = b"ARTIQ pc_rpc\n"


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
    :param expected_id_type: Server type to expect. ``IncompatibleServer`` is
        raised when the types do not match. Use ``None`` to accept any server
        type.

    """
    def __init__(self, host, port, expected_id_type):
        self.socket = socket.create_connection((host, port))
        self.socket.sendall(_init_string)
        self._identify(expected_id_type)

    def get_rpc_id(self):
        """Returns a dictionary containing the identification information of
        the server.

        """
        return self._server_identification

    def close_rpc(self):
        """Closes the connection to the RPC server.

        No further method calls should be done after this method is called.

        """
        self.socket.close()

    def _send_recv(self, obj):
        line = pyon.encode(obj) + "\n"
        self.socket.sendall(line.encode())

        buf = self.socket.recv(4096).decode()
        while "\n" not in buf:
            more = self.socket.recv(4096)
            if not more:
                break
            buf += more.decode()
        obj = pyon.decode(buf)

        return obj

    def _identify(self, expected_id_type):
        obj = {"action": "identify"}
        self._server_identification = self._send_recv(obj)
        if (expected_id_type is not None
                and self._server_identification["type"] != expected_id_type):
            raise IncompatibleServer

    def _do_rpc(self, name, args, kwargs):
        obj = {"action": "call", "name": name, "args": args, "kwargs": kwargs}
        obj = self._send_recv(obj)
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


class Server(AsyncioServer):
    """This class creates a TCP server that handles requests coming from
    ``Client`` objects.

    The server is designed using ``asyncio`` so that it can easily support
    multiple connections without the locking issues that arise in
    multi-threaded applications. Multiple connection support is useful even in
    simple cases: it allows new connections to be be accepted even when the
    previous client failed to properly shut down its connection.

    :param target: Object providing the RPC methods to be exposed to the
        client.
    :param id_type: A string identifying the server type. Clients use it to
        verify that they are connected to the proper server.
    :param id_parameters: An optional human-readable string giving more
        information about the parameters of the server.

    """
    def __init__(self, target, id_type, id_parameters=None):
        AsyncioServer.__init__(self)
        self.target = target
        self.id_type = id_type
        self.id_parameters = id_parameters

    @asyncio.coroutine
    def _handle_connection_cr(self, reader, writer):
        try:
            line = yield from reader.readline()
            if line != _init_string:
                return
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
                elif action == "identify":
                    obj = {"type": self.id_type}
                    if self.id_parameters is not None:
                        obj["parameters"] = self.id_parameters
                    line = pyon.encode(obj) + "\n"
                    writer.write(line.encode())
        finally:
            writer.close()


def simple_server_loop(target, id_type, host, port, id_parameters=None):
    """Runs a server until an exception is raised (e.g. the user hits Ctrl-C).

    See ``Server`` for a description of the parameters.

    """
    loop = asyncio.get_event_loop()
    try:
        server = Server(target, id_type, id_parameters)
        loop.run_until_complete(server.start(host, port))
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(server.stop())
    finally:
        loop.close()
