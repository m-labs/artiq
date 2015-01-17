"""
This module provides a remote procedure call (RPC) mechanism over sockets
between conventional computers (PCs) running Python. It strives to be
transparent and uses ``artiq.protocols.pyon`` internally so that e.g. Numpy
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

from artiq.protocols import pyon
from artiq.protocols.asyncio_server import AsyncioServer as _AsyncioServer


class RemoteError(Exception):
    """Raised when a RPC failed or raised an exception on the remote (server)
    side.

    """
    pass


class IncompatibleServer(Exception):
    """Raised by the client when attempting to connect to a server that does
    not have the expected target.

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
    :param target_name: Target name to select. ``IncompatibleServer`` is
        raised if the target does not exist.
        Use ``None`` to skip selecting a target. The list of targets can then
        be retrieved using ``get_rpc_id`` and then one can be selected later
        using ``select_rpc_target``.

    """
    def __init__(self, host, port, target_name):
        self.__socket = socket.create_connection((host, port))

        try:
            self.__socket.sendall(_init_string)

            server_identification = self.__recv()
            self.__target_names = server_identification["targets"]
            self.__id_parameters = server_identification["parameters"]
            if target_name is not None:
                self.select_rpc_target(target_name)
        except:
            self.__socket.close()
            raise

    def select_rpc_target(self, target_name):
        """Selects a RPC target by name. This function should be called
        exactly once if the object was created with ``target_name=None``.

        """
        if target_name not in self.__target_names:
            raise IncompatibleServer
        self.__socket.sendall((target_name + "\n").encode())

    def get_rpc_id(self):
        """Returns a tuple (target_names, id_parameters) containing the
        identification information of the server.

        """
        return (self.__target_names, self.__id_parameters)

    def close_rpc(self):
        """Closes the connection to the RPC server.

        No further method calls should be done after this method is called.

        """
        self.__socket.close()

    def __send(self, obj):
        line = pyon.encode(obj) + "\n"
        self.__socket.sendall(line.encode())

    def __recv(self):
        buf = self.__socket.recv(4096).decode()
        while "\n" not in buf:
            more = self.__socket.recv(4096)
            if not more:
                break
            buf += more.decode()
        return pyon.decode(buf)

    def __do_rpc(self, name, args, kwargs):
        obj = {"action": "call", "name": name, "args": args, "kwargs": kwargs}
        self.__send(obj)

        obj = self.__recv()
        if obj["status"] == "ok":
            return obj["ret"]
        elif obj["status"] == "failed":
            raise RemoteError(obj["message"])
        else:
            raise ValueError

    def __getattr__(self, name):
        def proxy(*args, **kwargs):
            return self.__do_rpc(name, args, kwargs)
        return proxy


class AsyncioClient:
    """This class is similar to :class:`artiq.protocols.pc_rpc.Client`, but
    uses ``asyncio`` instead of blocking calls.

    All RPC methods are coroutines.

    """
    def __init__(self):
        self.__lock = asyncio.Lock()
        self.__reader = None
        self.__writer = None
        self.__target_names = None
        self.__id_parameters = None

    @asyncio.coroutine
    def connect_rpc(self, host, port, target_name):
        """Connects to the server. This cannot be done in __init__ because
        this method is a coroutine. See ``Client`` for a description of the
        parameters.

        """
        self.__reader, self.__writer = \
            yield from asyncio.open_connection(host, port)
        try:
            self.__writer.write(_init_string)
            server_identification = yield from self.__recv()
            self.__target_names = server_identification["targets"]
            self.__id_parameters = server_identification["parameters"]
            if target_name is not None:
                self.select_rpc_target(target_name)
        except:
            self.close_rpc()
            raise

    def select_rpc_target(self, target_name):
        """Selects a RPC target by name. This function should be called
        exactly once if the connection was created with ``target_name=None``.

        """
        if target_name not in self.__target_names:
            raise IncompatibleServer
        self.__writer.write((target_name + "\n").encode())

    def get_rpc_id(self):
        """Returns a tuple (target_names, id_parameters) containing the
        identification information of the server.

        """
        return (self.__target_names, self.__id_parameters)

    def close_rpc(self):
        """Closes the connection to the RPC server.

        No further method calls should be done after this method is called.

        """
        self.__writer.close()
        self.__reader = None
        self.__writer = None
        self.__target_names = None
        self.__id_parameters = None

    def __send(self, obj):
        line = pyon.encode(obj) + "\n"
        self.__writer.write(line.encode())

    @asyncio.coroutine
    def __recv(self):
        line = yield from self.__reader.readline()
        return pyon.decode(line.decode())

    @asyncio.coroutine
    def __do_rpc(self, name, args, kwargs):
        yield from self.__lock.acquire()
        try:
            obj = {"action": "call", "name": name,
                   "args": args, "kwargs": kwargs}
            self.__send(obj)

            obj = yield from self.__recv()
            if obj["status"] == "ok":
                return obj["ret"]
            elif obj["status"] == "failed":
                raise RemoteError(obj["message"])
            else:
                raise ValueError
        finally:
            self.__lock.release()

    def __getattr__(self, name):
        @asyncio.coroutine
        def proxy(*args, **kwargs):
            return self.__do_rpc(name, args, kwargs)
        return proxy


class Server(_AsyncioServer):
    """This class creates a TCP server that handles requests coming from
    ``Client`` objects.

    The server is designed using ``asyncio`` so that it can easily support
    multiple connections without the locking issues that arise in
    multi-threaded applications. Multiple connection support is useful even in
    simple cases: it allows new connections to be be accepted even when the
    previous client failed to properly shut down its connection.

    :param targets: A dictionary of objects providing the RPC methods to be
        exposed to the client. Keys are names identifying each object.
        Clients select one of these objects using its name upon connection.
    :param id_parameters: An optional human-readable string giving more
        information about the parameters of the server.

    """
    def __init__(self, targets, id_parameters=None):
        _AsyncioServer.__init__(self)
        self.targets = targets
        self.id_parameters = id_parameters

    @asyncio.coroutine
    def _handle_connection_cr(self, reader, writer):
        try:
            line = yield from reader.readline()
            if line != _init_string:
                return

            obj = {
                "targets": sorted(self.targets.keys()),
                "parameters": self.id_parameters
            }
            line = pyon.encode(obj) + "\n"
            writer.write(line.encode())
            line = yield from reader.readline()
            if not line:
                return
            target_name = line.decode()[:-1]
            try:
                target = self.targets[target_name]
            except KeyError:
                return

            while True:
                line = yield from reader.readline()
                if not line:
                    break
                obj = pyon.decode(line.decode())
                try:
                    method = getattr(target, obj["name"])
                    ret = method(*obj["args"], **obj["kwargs"])
                    obj = {"status": "ok", "ret": ret}
                except Exception:
                    obj = {"status": "failed",
                           "message": traceback.format_exc()}
                line = pyon.encode(obj) + "\n"
                writer.write(line.encode())
        finally:
            writer.close()


def simple_server_loop(targets, host, port, id_parameters=None):
    """Runs a server until an exception is raised (e.g. the user hits Ctrl-C).

    See ``Server`` for a description of the parameters.

    """
    loop = asyncio.get_event_loop()
    try:
        server = Server(targets, id_parameters)
        loop.run_until_complete(server.start(host, port))
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(server.stop())
    finally:
        loop.close()
