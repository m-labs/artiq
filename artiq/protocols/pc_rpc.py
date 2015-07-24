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
import threading
import time
import logging
import inspect

from artiq.protocols import pyon
from artiq.protocols.asyncio_server import AsyncioServer as _AsyncioServer


logger = logging.getLogger(__name__)


class RemoteError(Exception):
    """Raised when a RPC failed or raised an exception on the remote (server)
    side."""
    pass


class IncompatibleServer(Exception):
    """Raised by the client when attempting to connect to a server that does
    not have the expected target."""
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
        exactly once if the object was created with ``target_name=None``."""
        if target_name not in self.__target_names:
            raise IncompatibleServer
        self.__socket.sendall((target_name + "\n").encode())

    def get_rpc_id(self):
        """Returns a tuple (target_names, id_parameters) containing the
        identification information of the server."""
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

    def __do_action(self, action):
        self.__send(action)

        obj = self.__recv()
        if obj["status"] == "ok":
            return obj["ret"]
        elif obj["status"] == "failed":
            raise RemoteError(obj["message"])
        else:
            raise ValueError

    def __do_rpc(self, name, args, kwargs):
        obj = {"action": "call", "name": name, "args": args, "kwargs": kwargs}
        return self.__do_action(obj)

    def get_rpc_method_list(self):
        obj = {"action": "get_rpc_method_list"}
        return self.__do_action(obj)

    def __getattr__(self, name):
        def proxy(*args, **kwargs):
            return self.__do_rpc(name, args, kwargs)
        return proxy


class AsyncioClient:
    """This class is similar to :class:`artiq.protocols.pc_rpc.Client`, but
    uses ``asyncio`` instead of blocking calls.

    All RPC methods are coroutines.

    Concurrent access from different asyncio tasks is supported; all calls
    use a single lock.
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
        parameters."""
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
        identification information of the server."""
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
            res = yield from self.__do_rpc(name, args, kwargs)
            return res
        return proxy


class BestEffortClient:
    """This class is similar to :class:`artiq.protocols.pc_rpc.Client`, but
    network errors are suppressed and connections are retried in the
    background.

    RPC calls that failed because of network errors return ``None``.

    :param firstcon_timeout: Timeout to use during the first (blocking)
        connection attempt at object initialization.
    :param retry: Amount of time to wait between retries when reconnecting
        in the background.
    """
    def __init__(self, host, port, target_name,
                 firstcon_timeout=0.5, retry=5.0):
        self.__host = host
        self.__port = port
        self.__target_name = target_name
        self.__retry = retry

        self.__conretry_terminate = False
        self.__socket = None
        try:
            self.__coninit(firstcon_timeout)
        except:
            logger.warning("first connection attempt to %s:%d[%s] failed, "
                           "retrying in the background",
                           self.__host, self.__port, self.__target_name)
            self.__start_conretry()
        else:
            self.__conretry_thread = None

    def __coninit(self, timeout):
        if timeout is None:
            self.__socket = socket.create_connection(
                (self.__host, self.__port))
        else:
            self.__socket = socket.create_connection(
                (self.__host, self.__port), timeout)
        self.__socket.sendall(_init_string)
        server_identification = self.__recv()
        if self.__target_name not in server_identification["targets"]:
            raise IncompatibleServer
        self.__socket.sendall((self.__target_name + "\n").encode())

    def __start_conretry(self):
        self.__conretry_thread = threading.Thread(target=self.__conretry)
        self.__conretry_thread.start()

    def __conretry(self):
        while True:
            try:
                self.__coninit(None)
            except:
                if self.__conretry_terminate:
                    break
                time.sleep(self.__retry)
            else:
                break
        if not self.__conretry_terminate:
            logger.warning("connection to %s:%d[%s] established in "
                           "the background",
                           self.__host, self.__port, self.__target_name)
        if self.__conretry_terminate and self.__socket is not None:
            self.__socket.close()
        # must be after __socket.close() to avoid race condition
        self.__conretry_thread = None

    def close_rpc(self):
        """Closes the connection to the RPC server.

        No further method calls should be done after this method is called.
        """
        if self.__conretry_thread is None:
            if self.__socket is not None:
                self.__socket.close()
        else:
            # Let the thread complete I/O and then do the socket closing.
            # Python fails to provide a way to cancel threads...
            self.__conretry_terminate = True

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
        if self.__conretry_thread is not None:
            return None

        obj = {"action": "call", "name": name, "args": args, "kwargs": kwargs}
        try:
            self.__send(obj)
            obj = self.__recv()
        except:
            logger.warning("connection failed while attempting "
                           "RPC to %s:%d[%s], re-establishing connection "
                           "in the background",
                           self.__host, self.__port, self.__target_name)
            self.__start_conretry()
            return None
        else:
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


def _format_arguments(arguments):
    fmtargs = []
    for k, v in sorted(arguments.items(), key=itemgetter(0)):
        fmtargs.append(k + "=" + repr(v))
    if fmtargs:
        return ", ".join(fmtargs)
    else:
        return ""


class _PrettyPrintCall:
    def __init__(self, obj):
        self.obj = obj

    def __str__(self):
        r = self.obj["name"] + "("
        args = ", ".join([repr(a) for a in self.obj["args"]])
        r += args
        kwargs = _format_arguments(self.obj["kwargs"])
        if args and kwargs:
            r += ", "
        r += kwargs
        r += ")"
        return r


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
                    if obj["action"] == "get_rpc_method_list":
                        members = inspect.getmembers(target, inspect.ismethod)
                        doc = {
                            "docstring": inspect.getdoc(target),
                            "methods": {}
                        }
                        for name, method in members:
                            if name.startswith("_"):
                                continue
                            method = getattr(target, name)
                            argspec = inspect.getfullargspec(method)
                            doc["methods"][name] = (dict(argspec.__dict__),
                                                    inspect.getdoc(method))
                        obj = {"status": "ok", "ret": doc}
                    elif obj["action"] == "call":
                        logger.debug("calling %s", _PrettyPrintCall(obj))
                        method = getattr(target, obj["name"])
                        ret = method(*obj["args"], **obj["kwargs"])
                        obj = {"status": "ok", "ret": ret}
                    else:
                        raise ValueError("Unknown action: {}"
                                         .format(obj["action"]))
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
