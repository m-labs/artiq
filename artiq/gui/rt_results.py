import asyncio
from collections import defaultdict

from gi.repository import Gtk
import cairoplot

from artiq.protocols.sync_struct import Subscriber
from artiq.gui.tools import Window


class _PlotWindow(Window):
    def __init__(self, set_names):
        self.set_names = set_names
        self.data = None

        Window.__init__(self, title="/".join(set_names),
                        default_size=(700, 500))

        self.darea = Gtk.DrawingArea()
        self.darea.set_size_request(100, 100)
        self.darea.connect("draw", self.on_draw)
        self.add(self.darea)

    def delete(self):
        self.close()


class XYWindow(_PlotWindow):
    def on_draw(self, widget, ctx):
        if self.data is not None:
            data = self.filter_data()
            cairoplot.scatter_plot(
                ctx,
                data=data,
                width=widget.get_allocated_width(),
                height=widget.get_allocated_height(),
                x_bounds=(min(data[0])*0.98, max(data[0])*1.02),
                y_bounds=(min(data[1])*0.98, max(data[1])*1.02),
                border=20, axis=True, grid=True,
                dots=1, discrete=True,
                series_colors=[(0.0, 0.0, 0.0)],
                background="white"
            )

    def filter_data(self):
        return [
            self.data[self.set_names[0]],
            self.data[self.set_names[1]],
        ]

    def set_data(self, data):
        self.data = data
        if not self.data:
            return
        # The two axes are not updated simultaneously.
        # Redraw only after receiving a new point for each.
        x, y = self.filter_data()
        if len(x) == len(y):
            self.darea.queue_draw()


def _create_view(set_names, view_description):
    r = XYWindow(set_names)
    r.show_all()
    return r


class _Group:
    def __init__(self, init):
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
                view = _create_view(set_names, view_description)
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
        self.groups[key] = _Group(value)

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
        if mod["action"] != "init" and len(mod["path"]) >= 3:
            path = mod["path"]
            group = self.current_groups[path[0]]
            if path[1] == "data":
                group.on_data_modified(path[2])
