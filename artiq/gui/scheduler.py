import time
import asyncio

from gi.repository import Gtk

from artiq.gui.tools import Window, DictSyncer
from artiq.protocols.sync_struct import Subscriber
from artiq.tools import format_arguments


class _ScheduleStoreSyncer(DictSyncer):
    def order_key(self, kv_pair):
        # order by due date, and then by RID
        return (kv_pair[1]["due_date"] or 0, kv_pair[0])

    def convert(self, rid, v):
        row = [rid, v["pipeline"], v["status"]]
        if v["due_date"] is None:
            row.append("")
        else:
            row.append(time.strftime("%m/%d %H:%M:%S",
                       time.localtime(v["due_date"])))
        row.append(v["expid"]["file"])
        if v["expid"]["experiment"] is None:
            row.append("")
        else:
            row.append(v["expid"]["experiment"])
        row.append(format_arguments(v["expid"]["arguments"]))
        return row


class SchedulerWindow(Window):
    def __init__(self, schedule_ctl, **kwargs):
        self.schedule_ctl = schedule_ctl

        Window.__init__(self,
                        title="Scheduler",
                        default_size=(950, 570),
                        **kwargs)

        topvbox = Gtk.VBox(spacing=6)
        self.add(topvbox)

        self.schedule_store = Gtk.ListStore(int, str, str, str, str, str, str)
        self.schedule_tree = Gtk.TreeView(self.schedule_store)
        for i, title in enumerate(["RID", "Pipeline", "Status", "Due date",
                                   "File", "Experiment", "Arguments"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            self.schedule_tree.append_column(column)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.schedule_tree)
        topvbox.pack_start(scroll, True, True, 0)
        button = Gtk.Button("Delete")
        button.connect("clicked", self.delete)
        topvbox.pack_start(button, False, False, 0)
        topvbox.set_border_width(6)

    def delete(self, widget):
        store, selected = self.schedule_tree.get_selection().get_selected()
        if selected is not None:
            rid = store[selected][0]
            asyncio.async(self.schedule_ctl.delete(rid))

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.schedule_subscriber = Subscriber("schedule", self.init_schedule_store)
        yield from self.schedule_subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.schedule_subscriber.close()

    def init_schedule_store(self, init):
        return _ScheduleStoreSyncer(self.schedule_store, init)
