import os

from gi.repository import Gtk


data_dir = os.path.abspath(os.path.dirname(__file__))


class Window(Gtk.Window):
    def __init__(self, *args, **kwargs):
        Gtk.Window.__init__(self, *args, **kwargs)
        self.set_wmclass("ARTIQ", "ARTIQ")
        self.set_icon_from_file(os.path.join(data_dir, "icon.png"))
        self.set_border_width(6)


class ListSyncer:
    def __init__(self, store, init):
        self.store = store
        self.store.clear()
        for x in init:
            self.append(x)

    def append(self, x):
        self.store.append(self.convert(x))

    def insert(self, i, x):
        self.store.insert(i, self.convert(x))

    def __delitem__(self, key):
        del self.store[key]
