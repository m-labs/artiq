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

    def convert(self, x):
        raise NotImplementedError


class DictSyncer:
    def __init__(self, store, init):
        self.store = store
        self.store.clear()
        self.order = []
        for k, v in sorted(init.items(), key=self.order_key):
            self.store.append(self.convert(k, v))
            self.order.append((k, self.order_key((k, v))))

    def _find_index(self, key):
        for i, e in enumerate(self.order):
            if e[0] == key:
                return i
        raise KeyError

    def __setitem__(self, key, value):
        try:
            i = self._find_index(key)
        except KeyError:
            pass
        else:
            del self.store[i]
            del self.order[i]
        ord_el = self.order_key((key, value))
        j = len(self.order)
        for i, (k, o) in enumerate(self.order):
            if o > ord_el:
                j = i
                break
        self.store.insert(j, self.convert(key, value))
        self.order.insert(j, (key, ord_el))

    def __delitem__(self, key):
        i = self._find_index(key)
        del self.store[i]
        del self.order[i]

    def order_key(self, kv_pair):
        raise NotImplementedError

    def convert(self, key, value):
        raise NotImplementedError
