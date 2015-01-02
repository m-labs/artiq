import asyncio
from operator import itemgetter
import time

from gi.repository import Gtk

from artiq.gui.tools import Window, ListSyncer
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


class _LastChangesStoreSyncer(ListSyncer):
    def convert(self, x):
        if len(x) == 3:
            timestamp, name, value = x
        else:
            timestamp, name = x
            value = "<deleted>"
        return [time.strftime("%m/%d %H:%M:%S", time.localtime(timestamp)),
                name, str(value)]


class ParametersWindow(Window):
    def __init__(self):
        Window.__init__(self, title="Parameters")
        self.set_default_size(500, 500)

        notebook = Gtk.Notebook()
        self.add(notebook)

        self.parameters_store = Gtk.ListStore(str, str)
        tree = Gtk.TreeView(self.parameters_store)
        for i, title in enumerate(["Parameter", "Value"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.add(tree)
        notebook.insert_page(scroll, Gtk.Label("Current values"), -1)

        self.lastchanges_store = Gtk.ListStore(str, str, str)
        tree = Gtk.TreeView(self.lastchanges_store)
        for i, title in enumerate(["Time", "Parameter", "Value"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.add(tree)
        notebook.insert_page(scroll, Gtk.Label("Last changes"), -1)

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.parameters_subscriber = Subscriber("parameters",
                                                self.init_parameters_store)
        yield from self.parameters_subscriber.connect(host, port)
        try:
            self.lastchanges_subscriber = Subscriber(
                "parameters_simplehist", self.init_lastchanges_store)
            yield from self.lastchanges_subscriber.connect(host, port)
        except:
            yield from self.parameters_subscriber.close()
            raise

    @asyncio.coroutine
    def sub_close(self):
        yield from self.lastchanges_subscriber.close()
        yield from self.parameters_subscriber.close()

    def init_parameters_store(self, init):
        return _ParameterStoreSyncer(self.parameters_store, init)

    def init_lastchanges_store(self, init):
        return _LastChangesStoreSyncer(self.lastchanges_store, init)
