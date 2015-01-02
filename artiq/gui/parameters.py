import asyncio
from operator import itemgetter

from gi.repository import Gtk

from artiq.gui.tools import Window
from artiq.management.sync_struct import Subscriber


class _ParameterStoreSyncer:
    def __init__(self, parameters_store, init):
        self.parameters_store = parameters_store
        self.parameters_store.clear()
        for name, value in sorted(init.items(), key=itemgetter(0)):
            self.parameters_store.append(self._convert(name, value))

    def _convert(self, name, value):
        return [name, str(value)]

    def _find_index(self, name):
        for i, e in enumerate(self.parameters_store):
            if e[0] == name:
                return i
        raise KeyError

    def __setitem__(self, name, value):
        try:
            i = self._find_index(name)
        except KeyError:
            pass
        else:
            del self.parameters_store[i]
        j = len(self.parameters_store)
        for i, e in enumerate(self.parameters_store):
            if e[0] > name:
                j = i
                break
        self.parameters_store.insert(j, self._convert(name, value))

    def __delitem__(self, key):
        del self.parameters_store[self._find_index(key)]


class ParametersWindow(Window):
    def __init__(self):
        Window.__init__(self, title="Parameters")
        self.set_default_size(500, 500)

        self.parameters_store = Gtk.ListStore(str, str)
        tree = Gtk.TreeView(self.parameters_store)
        for i, title in enumerate(["Parameter", "Value"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.add(tree)
        self.add(scroll)

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.parameters_subscriber = Subscriber("parameters",
                                                self.init_parameters_store)
        yield from self.parameters_subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.parameters_subscriber.close()

    def init_parameters_store(self, init):
        return _ParameterStoreSyncer(self.parameters_store, init)
