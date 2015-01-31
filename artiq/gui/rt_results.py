import asyncio
from collections import defaultdict

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.rt_result_views import RawWindow, XYWindow


def _create_view(group_name, set_names, view_description):
    if view_description == "raw":
        r = RawWindow(group_name, set_names)
    elif view_description == "xy":
        r = XYWindow(group_name, set_names)
    else:
        raise ValueError("Unknown view description: " + view_description)
    r.show_all()
    return r


class _Group:
    def __init__(self, name, init):
        self.name = name
        # data key -> list of views using it
        self.views = defaultdict(list)
        # original data
        self.data = dict()
        for k, v in init.items():
            self[k] = v

    def all_views(self):
        r = set()
        for view_list in self.views.values():
            for view in view_list:
                r.add(view)
        return r

    def delete(self):
        for view in self.all_views():
            view.delete()

    def __getitem__(self, key):
        if key == "data":
            return self.data
        else:
            raise KeyError

    def __setitem__(self, key, value):
        if key == "description":
            self.delete()
            self.views = defaultdict(list)
            for set_names, view_description in value.items():
                if not isinstance(set_names, tuple):
                    set_names = (set_names, )
                view = _create_view(self.name, set_names, view_description)
                view.set_data(self.data)
                for set_name in set_names:
                    self.views[set_name].append(view)
        elif key == "data":
            self.data = value
            for view in self.all_views():
                view.set_data(self.data)
        else:
            raise KeyError

    def on_data_modified(self, key):
        for view in self.views[key]:
            view.set_data(self.data)


class _Groups:
    def __init__(self, init):
        self.groups = dict()
        for k, v in init.items():
            self[k] = v

    def delete(self):
        for s in self.groups.values():
            s.delete()

    def __getitem__(self, key):
        return self.groups[key]

    def __setitem__(self, key, value):
        if key in self.groups:
            self.groups[key].delete()
        self.groups[key] = _Group(key, value)

    def __delitem__(self, key):
        self.groups[key].delete()
        del self.groups[key]


class RTResults:
    def __init__(self):
        self.current_groups = None

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.sets_subscriber = Subscriber("rt_results",
                                          self.init_groups, self.on_mod)
        yield from self.sets_subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.sets_subscriber.close()

    def init_groups(self, init):
        if self.current_groups is not None:
            self.current_groups.delete()
        self.current_groups = _Groups(init)
        return self.current_groups

    def on_mod(self, mod):
        if mod["action"] != "init" and len(mod["path"]) >= 2:
            path = mod["path"]
            group = self.current_groups[path[0]]
            if path[1] == "data":
                if len(mod["path"]) >= 3:
                    group.on_data_modified(path[2])
                else:
                    group.on_data_modified(mod["key"])
