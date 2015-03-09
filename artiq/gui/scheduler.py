import time
import asyncio

from gi.repository import Gtk

from artiq.gui.tools import Window, ListSyncer, DictSyncer
from artiq.protocols.sync_struct import Subscriber
from artiq.tools import format_arguments


class _QueueStoreSyncer(ListSyncer):
    def convert(self, x):
        rid, run_params = x
        row = [rid, run_params["file"]]
        if run_params["experiment"] is None:
            row.append("")
        else:
            row.append(run_params["experiment"])
        row.append(format_arguments(run_params["arguments"]))
        return row


class _TimedStoreSyncer(DictSyncer):
    def order_key(self, kv_pair):
        # order by next run time, and then by TRID
        return (kv_pair[1][0], kv_pair[0])

    def convert(self, trid, x):
        next_run, run_params = x
        row = [time.strftime("%m/%d %H:%M:%S", time.localtime(next_run)),
               trid, run_params["file"]]
        if run_params["experiment"] is None:
            row.append("")
        else:
            row.append(run_params["experiment"])
        row.append(format_arguments(run_params["arguments"]))
        return row


class SchedulerWindow(Window):
    def __init__(self, schedule_ctl, **kwargs):
        self.schedule_ctl = schedule_ctl

        Window.__init__(self,
                        title="Scheduler",
                        default_size=(720, 570),
                        **kwargs)

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
        for i, title in enumerate(["RID", "File", "Experiment", "Arguments"]):
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
        button.connect("clicked", self.remove_queued)
        hbox.pack_start(button, True, True, 0)
        vbox.pack_start(hbox, False, False, 0)
        vbox.set_border_width(6)
        notebook.insert_page(vbox, Gtk.Label("Queue"), -1)

        self.timed_store = Gtk.ListStore(str, int, str, str, str)
        self.timed_tree = Gtk.TreeView(self.timed_store)
        for i, title in enumerate(["Next run", "TRID", "File", "Experiment",
                                   "Arguments"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            self.timed_tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.timed_tree)
        vbox = Gtk.VBox(spacing=6)
        vbox.pack_start(scroll, True, True, 0)
        button = Gtk.Button("Remove")
        button.connect("clicked", self.remove_timed)
        vbox.pack_start(button, False, False, 0)
        vbox.set_border_width(6)
        notebook.insert_page(vbox, Gtk.Label("Timed schedule"), -1)

    def remove_queued(self, widget):
        store, selected = self.queue_tree.get_selection().get_selected()
        if selected is not None:
            rid = store[selected][0]
            asyncio.Task(self.schedule_ctl.cancel_queued(rid))

    def remove_timed(self, widget):
        store, selected = self.timed_tree.get_selection().get_selected()
        if selected is not None:
            trid = store[selected][1]
            asyncio.Task(self.schedule_ctl.cancel_timed(trid))

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.queue_subscriber = Subscriber("queue", self.init_queue_store)
        yield from self.queue_subscriber.connect(host, port)
        try:
            self.timed_subscriber = Subscriber("timed", self.init_timed_store)
            yield from self.timed_subscriber.connect(host, port)
        except:
            yield from self.queue_subscriber.close()
            raise

    @asyncio.coroutine
    def sub_close(self):
        yield from self.timed_subscriber.close()
        yield from self.queue_subscriber.close()

    def init_queue_store(self, init):
        return _QueueStoreSyncer(self.queue_store, init)

    def init_timed_store(self, init):
        return _TimedStoreSyncer(self.timed_store, init)
