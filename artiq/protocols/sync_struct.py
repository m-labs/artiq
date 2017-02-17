"""This module helps synchronizing a mutable Python structure owned and
modified by one process (the *publisher*) with copies of it (the
*subscribers*) in different processes and possibly different machines.

Synchronization is achieved by sending a full copy of the structure to each
subscriber upon connection (*initialization*), followed by dictionaries
describing each modification made to the structure (*mods*).

Structures must be PYON serializable and contain only lists, dicts, and
immutable types. Lists and dicts can be nested arbitrarily.
"""

import asyncio
from operator import getitem
from functools import partial

from artiq.monkey_patches import *
from artiq.protocols import pyon
from artiq.protocols.asyncio_server import AsyncioServer


_init_string = b"ARTIQ sync_struct\n"


def process_mod(target, mod):
    """Apply a *mod* to the target, mutating it."""
    for key in mod["path"]:
        target = getitem(target, key)
    action = mod["action"]
    if action == "append":
        target.append(mod["x"])
    elif action == "insert":
        target.insert(mod["i"], mod["x"])
    elif action == "pop":
        target.pop(mod["i"])
    elif action == "setitem":
        target.__setitem__(mod["key"], mod["value"])
    elif action == "delitem":
        target.__delitem__(mod["key"])
    else:
        raise ValueError


class Subscriber:
    """An asyncio-based client to connect to a ``Publisher``.

    :param notifier_name: Name of the notifier to subscribe to.
    :param target_builder: A function called during initialization that takes
        the object received from the publisher and returns the corresponding
        local structure to use. Can be identity.
    :param notify_cb: An optional function called every time a mod is received
        from the publisher. The mod is passed as parameter. The function is
        called after the mod has been processed.
        A list of functions may also be used, and they will be called in turn.
    :param disconnect_cb: An optional function called when disconnection happens
        from external causes (i.e. not when ``close`` is called).
    """
    def __init__(self, notifier_name, target_builder, notify_cb=None, disconnect_cb=None):
        self.notifier_name = notifier_name
        self.target_builder = target_builder
        if notify_cb is None:
            notify_cb = []
        if not isinstance(notify_cb, list):
            notify_cb = [notify_cb]
        self.notify_cbs = notify_cb
        self.disconnect_cb = disconnect_cb

    async def connect(self, host, port, before_receive_cb=None):
        self.reader, self.writer = \
            await asyncio.open_connection(host, port, limit=100*1024*1024)
        try:
            if before_receive_cb is not None:
                before_receive_cb()
            self.writer.write(_init_string)
            self.writer.write((self.notifier_name + "\n").encode())
            self.receive_task = asyncio.ensure_future(self._receive_cr())
        except:
            self.writer.close()
            del self.reader
            del self.writer
            raise

    async def close(self):
        self.disconnect_cb = None
        try:
            self.receive_task.cancel()
            try:
                await asyncio.wait_for(self.receive_task, None)
            except asyncio.CancelledError:
                pass
        finally:
            self.writer.close()
            del self.reader
            del self.writer

    async def _receive_cr(self):
        try:
            target = None
            while True:
                line = await self.reader.readline()
                if not line:
                    return
                mod = pyon.decode(line.decode())

                if mod["action"] == "init":
                    target = self.target_builder(mod["struct"])
                else:
                    process_mod(target, mod)

                for notify_cb in self.notify_cbs:
                    notify_cb(mod)
        finally:
            if self.disconnect_cb is not None:
                self.disconnect_cb()


class Notifier:
    """Encapsulates a structure whose changes need to be published.

    All mutations to the structure must be made through the ``Notifier``. The
    original structure must only be accessed for reads.

    In addition to the list methods below, the ``Notifier`` supports the index
    syntax for modification and deletion of elements. Modification of nested
    structures can be also done using the index syntax, for example:

    >>> n = Notifier([])
    >>> n.append([])
    >>> n[0].append(42)
    >>> n.read
    [[42]]

    This class does not perform any network I/O and is meant to be used with
    e.g. the ``Publisher`` for this purpose. Only one publisher at most can be
    associated with a ``Notifier``.

    :param backing_struct: Structure to encapsulate. For convenience, it
        also becomes available as the ``read`` property of the ``Notifier``.
    """
    def __init__(self, backing_struct, root=None, path=[]):
        self.read = backing_struct
        if root is None:
            self.root = self
            self.publish = None
        else:
            self.root = root
        self._backing_struct = backing_struct
        self._path = path

    # Backing struct modification methods.
    # All modifications must go through them!

    def append(self, x):
        """Append to a list."""
        self._backing_struct.append(x)
        if self.root.publish is not None:
            self.root.publish({"action": "append",
                               "path": self._path,
                               "x": x})

    def insert(self, i, x):
        """Insert an element into a list."""
        self._backing_struct.insert(i, x)
        if self.root.publish is not None:
            self.root.publish({"action": "insert",
                               "path": self._path,
                               "i": i, "x": x})

    def pop(self, i=-1):
        """Pop an element from a list. The returned element is not
        encapsulated in a ``Notifier`` and its mutations are no longer
        tracked."""
        r = self._backing_struct.pop(i)
        if self.root.publish is not None:
            self.root.publish({"action": "pop",
                               "path": self._path,
                               "i": i})
        return r

    def __setitem__(self, key, value):
        self._backing_struct.__setitem__(key, value)
        if self.root.publish is not None:
            self.root.publish({"action": "setitem",
                               "path": self._path,
                               "key": key,
                               "value": value})

    def __delitem__(self, key):
        self._backing_struct.__delitem__(key)
        if self.root.publish is not None:
            self.root.publish({"action": "delitem",
                               "path": self._path,
                               "key": key})

    def __getitem__(self, key):
        item = getitem(self._backing_struct, key)
        return Notifier(item, self.root, self._path + [key])


class Publisher(AsyncioServer):
    """A network server that publish changes to structures encapsulated in
    ``Notifiers``.

    :param notifiers: A dictionary containing the notifiers to associate with
        the ``Publisher``. The keys of the dictionary are the names of the
        notifiers to be used with ``Subscriber``.
    """
    def __init__(self, notifiers):
        AsyncioServer.__init__(self)
        self.notifiers = notifiers
        self._recipients = {k: set() for k in notifiers.keys()}
        self._notifier_names = {id(v): k for k, v in notifiers.items()}

        for notifier in notifiers.values():
            notifier.publish = partial(self.publish, notifier)

    async def _handle_connection_cr(self, reader, writer):
        try:
            line = await reader.readline()
            if line != _init_string:
                return

            line = await reader.readline()
            if not line:
                return
            notifier_name = line.decode()[:-1]

            try:
                notifier = self.notifiers[notifier_name]
            except KeyError:
                return

            obj = {"action": "init", "struct": notifier.read}
            line = pyon.encode(obj) + "\n"
            writer.write(line.encode())

            queue = asyncio.Queue()
            self._recipients[notifier_name].add(queue)
            try:
                while True:
                    line = await queue.get()
                    writer.write(line)
                    # raise exception on connection error
                    await writer.drain()
            finally:
                self._recipients[notifier_name].remove(queue)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            # subscribers disconnecting are a normal occurence
            pass
        finally:
            writer.close()

    def publish(self, notifier, mod):
        line = pyon.encode(mod) + "\n"
        line = line.encode()
        notifier_name = self._notifier_names[id(notifier)]
        for recipient in self._recipients[notifier_name]:
            recipient.put_nowait(line)
