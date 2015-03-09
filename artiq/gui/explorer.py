import asyncio
import types

from gi.repository import Gtk

from artiq.gui.tools import Window, getitem, DictSyncer
from artiq.protocols.sync_struct import Subscriber


class _ExplistStoreSyncer(DictSyncer):
    def order_key(self, kv_pair):
        return kv_pair[0]

    def convert(self, name, value):
        return [name]


class ExplorerWindow(Window):
    def __init__(self, exit_fn, schedule_ctl, repository, layout_dict=dict()):
        self.schedule_ctl = schedule_ctl
        self.repository = repository

        Window.__init__(self,
                        title="Explorer",
                        default_size=(800, 570),
                        layout_dict=layout_dict)
        self.connect("delete-event", exit_fn)

        topvbox = Gtk.VBox(spacing=6)
        self.add(topvbox)

        menubar = Gtk.MenuBar()
        topvbox.pack_start(menubar, False, False, 0)

        top_menuitem = Gtk.MenuItem("Windows")
        menu = Gtk.Menu()
        menuitem = Gtk.MenuItem("Scheduler")
        menu.append(menuitem)
        menuitem = Gtk.MenuItem("Parameters")
        menu.append(menuitem)
        menu.append(Gtk.SeparatorMenuItem())
        menuitem = Gtk.MenuItem("Quit")
        menuitem.connect("activate", exit_fn)
        menu.append(menuitem)
        top_menuitem.set_submenu(menu)
        menubar.append(top_menuitem)

        top_menuitem = Gtk.MenuItem("Registry")
        menu = Gtk.Menu()
        menuitem = Gtk.MenuItem("Run selected")
        menuitem.connect("activate", self.run)
        menu.append(menuitem)
        menu.append(Gtk.SeparatorMenuItem())
        menuitem = Gtk.MenuItem("Add experiment")
        menu.append(menuitem)
        menuitem = Gtk.MenuItem("Remove experiment")
        menu.append(menuitem)
        top_menuitem.set_submenu(menu)
        menubar.append(top_menuitem)

        self.pane = Gtk.HPaned(
            position=getitem(layout_dict, "pane_position", 180))
        topvbox.pack_start(self.pane, True, True, 0)

        explistvbox = Gtk.VBox(spacing=6)
        self.pane.pack1(explistvbox)
        self.explist_store = Gtk.ListStore(str)
        self.explist_tree = Gtk.TreeView(self.explist_store)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Registered experiments", renderer, text=0)
        self.explist_tree.append_column(column)
        self.explist_tree.connect("row-activated", self.explist_row_activated)
        self.explist_tree.set_activate_on_single_click(True)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.explist_tree)
        explistvbox.pack_start(scroll, True, True, 0)
        button = Gtk.Button("Run")
        button.connect("clicked", self.run)
        explistvbox.pack_start(button, False, False, 0)

        self.pane_contents = Gtk.Label("")
        self.pane.pack2(self.pane_contents)

    def get_layout_dict(self):
        r = Window.get_layout_dict(self)
        r["pane_position"] = self.pane.get_position()
        return r

    @asyncio.coroutine
    def sub_connect(self, host, port):
        self.explist_subscriber = Subscriber("explist",
                                             [self.init_explist_store,
                                              self.init_explist_data])
        yield from self.explist_subscriber.connect(host, port)

    @asyncio.coroutine
    def sub_close(self):
        yield from self.explist_subscriber.close()

    def init_parameters_dict(self, init):
        self.parameters = init
        return init

    def set_pane_contents(self, widget):
        self.pane_contents.destroy()
        self.pane_contents = widget
        self.pane.pack2(self.pane_contents)
        self.pane_contents.show_all()

    def init_explist_store(self, init):
        return _ExplistStoreSyncer(self.explist_store, init)

    def init_explist_data(self, init):
        self.explist_data = init
        return init

    def explist_row_activated(self, widget, index, column):
        self.controls = None
        name = self.explist_store[index][0]
        gui_file = self.explist_data[name]["gui_file"]
        if gui_file is None:
            self.set_pane_contents(Gtk.Label("No GUI controls"))
        else:
            asyncio.Task(self.load_gui_file(gui_file))

    @asyncio.coroutine
    def load_gui_file(self, gui_file):
        gui_mod_data = yield from self.repository.get_data(gui_file)
        gui_mod = dict()
        exec(gui_mod_data, gui_mod)
        facilities = types.SimpleNamespace(
            get_data=self.repository.get_data,
            get_parameter=lambda p: self.parameters[p])
        self.controls = gui_mod["Controls"](facilities)
        yield from self.controls.build()
        self.set_pane_contents(self.controls.get_top_widget())

    def run(self, widget):
        store, selected = self.explist_tree.get_selection().get_selected()
        if selected is not None:
            name = store[selected][0]
            data = self.explist_data[name]
            if self.controls is None:
                arguments = {}
            else:
                arguments = self.controls.get_arguments()
            run_params = {
                "file": data["file"],
                "experiment": data["experiment"],
                "arguments": arguments,
                "rtr_group": data["file"]
            }
            asyncio.Task(self.schedule_ctl.run_queued(run_params))
