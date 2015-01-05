import time
import asyncio

from gi.repository import Gtk

from artiq.gui.tools import Window, ListSyncer, DictSyncer
from artiq.management.sync_struct import Subscriber


class _QueueStoreSyncer(ListSyncer):
    def convert(self, x):
        rid, run_params, timeout = x
        row = [rid, run_params["file"]]
        for e in run_params["unit"], timeout:
            row.append("-" if e is None else str(e))
        return row


class _PeriodicStoreSyncer(DictSyncer):
    def order_key(self, kv_pair):
        # order by next run time, and then by PRID
        return (kv_pair[1][0], kv_pair[0])

    def convert(self, prid, x):
        next_run, run_params, timeout, period = x
        row = [time.strftime("%m/%d %H:%M:%S", time.localtime(next_run)),
               prid, run_params["file"]]
        for e in run_params["unit"], timeout:
            row.append("-" if e is None else str(e))
        row.append(str(period))
        return row


class SchedulerWindow(Window):
    def __init__(self, schedule_ctl):
        self.schedule_ctl = schedule_ctl

        Window.__init__(self, title="Scheduler")
        self.set_default_size(720, 570)

        topvbox = Gtk.VBox(spacing=6)
        self.add(topvbox)

        hbox = Gtk.HBox(spacing=6)
        enable = Gtk.Switch(active=True)
        label = Gtk.Label("Run experiments")
        hbox.pack_start(label, False, False, 0)
        hbox.pack_start(enable, False, False, 0)
        topvbox.pack_start(hbox, False, False, 0)

        notebook = Gtk.Notebook()
        topvbox.pack_start(notebook, True, True, 0)

        self.queue_store = Gtk.ListStore(int, str, str, str)
        self.queue_tree = Gtk.TreeView(self.queue_store)
        for i, title in enumerate(["RID", "File", "Unit", "Timeout"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            self.queue_tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.queue_tree)
        vbox = Gtk.VBox(spacing=6)
        vbox.pack_start(scroll, True, True, 0)
        hbox = Gtk.HBox(spacing=6)
        button = Gtk.Button("Find")
        hbox.pack_start(button, True, True, 0)
        button = Gtk.Button("Move up")
        hbox.pack_start(button, True, True, 0)
        button = Gtk.Button("Move down")
        hbox.pack_start(button, True, True, 0)
        button = Gtk.Button("Remove")
        button.connect("clicked", self.remove_queue)
        hbox.pack_start(button, True, True, 0)
        vbox.pack_start(hbox, False, False, 0)
        vbox.set_border_width(6)
        notebook.insert_page(vbox, Gtk.Label("Queue"), -1)

        self.periodic_store = Gtk.ListStore(str, int, str, str, str, str)
        self.periodic_tree = Gtk.TreeView(self.periodic_store)
        for i, title in enumerate(["Next run", "PRID", "File", "Unit",
                                   "Timeout", "Period"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            self.periodic_tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.periodic_tree)
        vbox = Gtk.VBox(spacing=6)
        vbox.pack_start(scroll, True, True, 0)
        hbox = Gtk.HBox(spacing=6)
        button = Gtk.Button("Change period")
        hbox.pack_start(button, True, True, 0)
        button = Gtk.Button("Remove")
        button.connect("clicked", self.remove_periodic)
        hbox.pack_start(button, True, True, 0)
        vbox.pack_start(hbox, False, False, 0)
        vbox.set_border_width(6)
        notebook.insert_page(vbox, Gtk.Label("Periodic schedule"), -1)

    def remove_queue(self, widget):
        store, selected = self.queue_tree.get_selection().get_selected()
        if selected is not None:
            rid = store[selected][0]
            asyncio.Task(self.schedule_ctl.cancel_once(rid))

    def remove_periodic(self, widget):
        store, selected = self.periodic_tree.get_selection().get_selected()
        if selected is not None:
            prid = store[selected][1]
            asyncio.Task(self.schedule_ctl.cancel_periodic(prid))

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.queue_subscriber = Subscriber("queue", self.init_queue_store)
        yield from self.queue_subscriber.connect(host, port)
        try:
            self.periodic_subscriber = Subscriber(
                "periodic", self.init_periodic_store)
            yield from self.periodic_subscriber.connect(host, port)
        except:
            yield from self.queue_subscriber.close()
            raise

    @asyncio.coroutine
    def sub_close(self):
        yield from self.periodic_subscriber.close()
        yield from self.queue_subscriber.close()

    def init_queue_store(self, init):
        return _QueueStoreSyncer(self.queue_store, init)

    def init_periodic_store(self, init):
        return _PeriodicStoreSyncer(self.periodic_store, init)
